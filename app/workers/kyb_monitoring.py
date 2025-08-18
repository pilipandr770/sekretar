"""KYB monitoring worker for counterparty data collection and monitoring."""
import logging
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from flask import current_app
from sqlalchemy import and_, or_
from app import db
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, CounterpartyDiff, 
    KYBAlert, KYBMonitoringConfig
)
from app.services.kyb_service import KYBService
from app.services.sanctions_service import SanctionsMonitoringService
from app.workers.base import MonitoredWorker, create_task_decorator

logger = logging.getLogger(__name__)

# Create task decorator for KYB monitoring queue
kyb_task = create_task_decorator('kyb_monitoring', max_retries=3, default_retry_delay=300)


@kyb_task
def collect_counterparty_data(counterparty_id: int, check_types: List[str] = None) -> Dict[str, Any]:
    """
    Collect data for a specific counterparty from external sources.
    
    Args:
        counterparty_id: Counterparty ID to check
        check_types: List of check types to perform (vat, lei, sanctions, insolvency)
    
    Returns:
        Dict with collection results
    """
    try:
        logger.info(f"Starting data collection for counterparty {counterparty_id}")
        
        # Get counterparty
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            raise ValueError(f"Counterparty {counterparty_id} not found")
        
        if not counterparty.monitoring_enabled:
            logger.info(f"Monitoring disabled for counterparty {counterparty_id}")
            return {
                'counterparty_id': counterparty_id,
                'status': 'skipped',
                'reason': 'monitoring_disabled'
            }
        
        # Get monitoring config
        config = KYBMonitoringConfig.query.filter_by(
            tenant_id=counterparty.tenant_id
        ).first()
        
        if not config:
            logger.warning(f"No monitoring config found for tenant {counterparty.tenant_id}")
            config = KYBMonitoringConfig(tenant_id=counterparty.tenant_id)
            db.session.add(config)
            db.session.commit()
        
        # Determine which checks to perform
        if not check_types:
            check_types = _determine_check_types(counterparty, config)
        
        collection_results = []
        snapshots_created = []
        
        # Perform each check type
        for check_type in check_types:
            try:
                result = _perform_data_check(counterparty, check_type, config)
                if result:
                    collection_results.append(result)
                    
                    # Create snapshot
                    snapshot = _create_snapshot(counterparty, check_type, result)
                    if snapshot:
                        snapshots_created.append(snapshot.id)
                        
            except Exception as e:
                logger.error(f"Error performing {check_type} check for counterparty {counterparty_id}: {e}")
                collection_results.append({
                    'check_type': check_type,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Update counterparty last checked time
        counterparty.last_checked = datetime.utcnow()
        counterparty.next_check = _calculate_next_check_time(counterparty, config)
        db.session.commit()
        
        result = {
            'counterparty_id': counterparty_id,
            'tenant_id': counterparty.tenant_id,
            'check_types': check_types,
            'collection_results': collection_results,
            'snapshots_created': snapshots_created,
            'collected_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed data collection for counterparty {counterparty_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in collect_counterparty_data: {e}")
        raise


@kyb_task
def detect_counterparty_changes(counterparty_id: int, new_snapshot_id: int) -> Dict[str, Any]:
    """
    Detect changes between the latest snapshot and previous snapshots.
    
    Args:
        counterparty_id: Counterparty ID
        new_snapshot_id: ID of the new snapshot to compare
    
    Returns:
        Dict with change detection results
    """
    try:
        logger.info(f"Starting change detection for counterparty {counterparty_id}")
        
        # Get the new snapshot
        new_snapshot = CounterpartySnapshot.query.get(new_snapshot_id)
        if not new_snapshot:
            raise ValueError(f"Snapshot {new_snapshot_id} not found")
        
        # Get the previous snapshot of the same type
        previous_snapshot = CounterpartySnapshot.query.filter(
            and_(
                CounterpartySnapshot.counterparty_id == counterparty_id,
                CounterpartySnapshot.check_type == new_snapshot.check_type,
                CounterpartySnapshot.id != new_snapshot_id,
                CounterpartySnapshot.status == 'valid'
            )
        ).order_by(CounterpartySnapshot.created_at.desc()).first()
        
        if not previous_snapshot:
            logger.info(f"No previous snapshot found for comparison")
            return {
                'counterparty_id': counterparty_id,
                'new_snapshot_id': new_snapshot_id,
                'changes_detected': 0,
                'status': 'no_previous_snapshot'
            }
        
        # Compare snapshots
        changes = _compare_snapshots(previous_snapshot, new_snapshot)
        
        # Get counterparty for tenant_id
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            raise ValueError(f"Counterparty {counterparty_id} not found")
        
        # Create diff records
        diffs_created = []
        for change in changes:
            diff = CounterpartyDiff(
                tenant_id=counterparty.tenant_id,
                counterparty_id=counterparty_id,
                old_snapshot_id=previous_snapshot.id,
                new_snapshot_id=new_snapshot_id,
                field_path=change['field_path'],
                old_value=change['old_value'],
                new_value=change['new_value'],
                change_type=change['change_type'],
                risk_impact=change['risk_impact'],
                risk_score_delta=change['risk_score_delta']
            )
            db.session.add(diff)
            db.session.flush()
            diffs_created.append(diff.id)
        
        db.session.commit()
        
        result = {
            'counterparty_id': counterparty_id,
            'new_snapshot_id': new_snapshot_id,
            'previous_snapshot_id': previous_snapshot.id,
            'changes_detected': len(changes),
            'diffs_created': diffs_created,
            'detected_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed change detection for counterparty {counterparty_id}: {len(changes)} changes")
        return result
        
    except Exception as e:
        logger.error(f"Error in detect_counterparty_changes: {e}")
        raise


@kyb_task
def generate_kyb_alerts(counterparty_id: int, diff_ids: List[int] = None) -> Dict[str, Any]:
    """
    Generate alerts based on detected changes or risk conditions.
    
    Args:
        counterparty_id: Counterparty ID
        diff_ids: Optional list of specific diff IDs to process
    
    Returns:
        Dict with alert generation results
    """
    try:
        logger.info(f"Starting alert generation for counterparty {counterparty_id}")
        
        # Get counterparty and config
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            raise ValueError(f"Counterparty {counterparty_id} not found")
        
        config = KYBMonitoringConfig.query.filter_by(
            tenant_id=counterparty.tenant_id
        ).first()
        
        if not config:
            logger.warning(f"No monitoring config found for tenant {counterparty.tenant_id}")
            return {
                'counterparty_id': counterparty_id,
                'alerts_generated': 0,
                'status': 'no_config'
            }
        
        # Get diffs to process
        if diff_ids:
            diffs = CounterpartyDiff.query.filter(
                and_(
                    CounterpartyDiff.id.in_(diff_ids),
                    CounterpartyDiff.counterparty_id == counterparty_id,
                    CounterpartyDiff.processed == False
                )
            ).all()
        else:
            # Get all unprocessed diffs for this counterparty
            diffs = CounterpartyDiff.query.filter(
                and_(
                    CounterpartyDiff.counterparty_id == counterparty_id,
                    CounterpartyDiff.processed == False
                )
            ).all()
        
        alerts_generated = []
        
        # Process each diff
        for diff in diffs:
            try:
                alert = _generate_alert_from_diff(diff, config)
                if alert:
                    db.session.add(alert)
                    db.session.flush()
                    alerts_generated.append(alert.id)
                    
                    # Mark diff as processed
                    diff.processed = True
                    diff.alert_generated = True
                    
            except Exception as e:
                logger.error(f"Error generating alert for diff {diff.id}: {e}")
        
        # Check for risk-based alerts (sanctions, high risk score, etc.)
        risk_alerts = _generate_risk_based_alerts(counterparty, config)
        for alert in risk_alerts:
            db.session.add(alert)
            db.session.flush()
            alerts_generated.append(alert.id)
        
        # Update counterparty risk score
        _update_counterparty_risk_score(counterparty)
        
        db.session.commit()
        
        result = {
            'counterparty_id': counterparty_id,
            'diffs_processed': len(diffs),
            'alerts_generated': len(alerts_generated),
            'alert_ids': alerts_generated,
            'generated_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed alert generation for counterparty {counterparty_id}: {len(alerts_generated)} alerts")
        return result
        
    except Exception as e:
        logger.error(f"Error in generate_kyb_alerts: {e}")
        raise


@kyb_task
def create_evidence_snapshot(snapshot_id: int) -> Dict[str, Any]:
    """
    Create and store evidence files for compliance purposes.
    
    Args:
        snapshot_id: Snapshot ID to create evidence for
    
    Returns:
        Dict with evidence creation results
    """
    try:
        logger.info(f"Starting evidence creation for snapshot {snapshot_id}")
        
        # Get snapshot
        snapshot = CounterpartySnapshot.query.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")
        
        # Create evidence directory structure
        evidence_dir = _create_evidence_directory(snapshot)
        
        # Generate evidence files
        evidence_files = []
        
        # 1. Raw API response
        raw_file = _save_raw_response(snapshot, evidence_dir)
        if raw_file:
            evidence_files.append(raw_file)
        
        # 2. Processed data summary
        summary_file = _save_data_summary(snapshot, evidence_dir)
        if summary_file:
            evidence_files.append(summary_file)
        
        # 3. Compliance report
        compliance_file = _save_compliance_report(snapshot, evidence_dir)
        if compliance_file:
            evidence_files.append(compliance_file)
        
        # Update snapshot with evidence path
        snapshot.evidence_stored = True
        snapshot.evidence_path = evidence_dir
        db.session.commit()
        
        result = {
            'snapshot_id': snapshot_id,
            'counterparty_id': snapshot.counterparty_id,
            'evidence_directory': evidence_dir,
            'evidence_files': evidence_files,
            'created_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed evidence creation for snapshot {snapshot_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in create_evidence_snapshot: {e}")
        raise


@kyb_task
def schedule_counterparty_monitoring(tenant_id: int = None) -> Dict[str, Any]:
    """
    Schedule monitoring tasks for counterparties based on their monitoring frequency.
    
    Args:
        tenant_id: Optional tenant ID to limit scheduling to specific tenant
    
    Returns:
        Dict with scheduling results
    """
    try:
        logger.info("Starting counterparty monitoring scheduling")
        
        # Get counterparties that need checking
        now = datetime.utcnow()
        query = Counterparty.query.filter(
            and_(
                Counterparty.monitoring_enabled == True,
                or_(
                    Counterparty.next_check.is_(None),
                    Counterparty.next_check <= now
                )
            )
        )
        
        if tenant_id:
            query = query.filter(Counterparty.tenant_id == tenant_id)
        
        counterparties = query.all()
        
        scheduled_tasks = []
        
        for counterparty in counterparties:
            try:
                # Schedule data collection task
                task = collect_counterparty_data.apply_async(
                    args=[counterparty.id],
                    countdown=0  # Execute immediately
                )
                
                scheduled_tasks.append({
                    'counterparty_id': counterparty.id,
                    'task_id': task.id,
                    'scheduled_at': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error scheduling monitoring for counterparty {counterparty.id}: {e}")
                scheduled_tasks.append({
                    'counterparty_id': counterparty.id,
                    'error': str(e)
                })
        
        result = {
            'tenant_id': tenant_id,
            'counterparties_checked': len(counterparties),
            'tasks_scheduled': len([t for t in scheduled_tasks if 'error' not in t]),
            'scheduling_errors': len([t for t in scheduled_tasks if 'error' in t]),
            'scheduled_tasks': scheduled_tasks,
            'scheduled_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed monitoring scheduling: {result['tasks_scheduled']} tasks scheduled")
        return result
        
    except Exception as e:
        logger.error(f"Error in schedule_counterparty_monitoring: {e}")
        raise


# Helper functions

def _determine_check_types(counterparty: Counterparty, config: KYBMonitoringConfig) -> List[str]:
    """Determine which check types to perform based on counterparty data and config."""
    check_types = []
    
    # VAT check
    if counterparty.vat_number and counterparty.country_code and config.vies_enabled:
        check_types.append('vat')
    
    # LEI check
    if counterparty.lei_code and config.gleif_enabled:
        check_types.append('lei')
    
    # Sanctions checks
    if counterparty.name:
        if config.sanctions_eu_enabled:
            check_types.append('sanctions_eu')
        if config.sanctions_ofac_enabled:
            check_types.append('sanctions_ofac')
        if config.sanctions_uk_enabled:
            check_types.append('sanctions_uk')
    
    # Insolvency check (Germany only for now)
    if (counterparty.country_code == 'DE' and 
        counterparty.registration_number and 
        config.insolvency_de_enabled):
        check_types.append('insolvency_de')
    
    return check_types


def _perform_data_check(counterparty: Counterparty, check_type: str, 
                       config: KYBMonitoringConfig) -> Optional[Dict[str, Any]]:
    """Perform a specific type of data check."""
    try:
        if check_type == 'vat':
            return KYBService.check_vat_number(
                counterparty.vat_number, 
                counterparty.country_code
            )
        
        elif check_type == 'lei':
            result = KYBService.check_lei_code(counterparty.lei_code)
            
            # Enhance result with additional LEI-specific data
            if result.get('status') == 'valid':
                result['lei_code'] = counterparty.lei_code
                result['entity_status'] = result.get('entity_status')
                result['legal_name'] = result.get('legal_name')
                result['legal_form'] = result.get('legal_form')
                result['registration_authority'] = result.get('registration_authority')
                result['legal_address'] = result.get('legal_address')
                result['headquarters_address'] = result.get('headquarters_address')
            
            return result
        
        elif check_type.startswith('sanctions'):
            # For sanctions, we get a list of matches
            matches = KYBService.check_sanctions(
                counterparty.name, 
                counterparty.country_code
            )
            
            # Filter matches based on check type
            if check_type == 'sanctions_eu':
                matches = [m for m in matches if 'EU' in m.get('list', '')]
            elif check_type == 'sanctions_ofac':
                matches = [m for m in matches if 'OFAC' in m.get('list', '')]
            elif check_type == 'sanctions_uk':
                matches = [m for m in matches if 'UK' in m.get('list', '')]
            
            return {
                'status': 'checked',
                'matches': matches,
                'match_count': len(matches),
                'source': check_type.upper(),
                'checked_at': datetime.utcnow().isoformat()
            }
        
        elif check_type == 'insolvency_de':
            # German insolvency check using InsolvencyMonitoringService
            from app.services.insolvency_service import InsolvencyMonitoringService
            
            insolvency_service = InsolvencyMonitoringService()
            result = insolvency_service.check_counterparty_insolvency(counterparty.id)
            
            # Extract the check result from the service response
            check_result = result.get('check_result', {})
            
            return {
                'status': check_result.get('status', 'checked'),
                'proceedings_found': check_result.get('proceedings_found', False),
                'proceedings_count': check_result.get('proceedings_count', 0),
                'proceedings': check_result.get('proceedings', []),
                'risk_analysis': check_result.get('risk_analysis', {}),
                'source': 'INSOLVENCY_DE',
                'checked_at': datetime.utcnow().isoformat(),
                'response_time_ms': check_result.get('response_time_ms')
            }
        
        else:
            logger.warning(f"Unknown check type: {check_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error performing {check_type} check: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'source': check_type.upper(),
            'checked_at': datetime.utcnow().isoformat()
        }


def _create_snapshot(counterparty: Counterparty, check_type: str, 
                    result: Dict[str, Any]) -> Optional[CounterpartySnapshot]:
    """Create a snapshot record from check result."""
    try:
        # Calculate data hash
        data_hash = hashlib.sha256(
            json.dumps(result, sort_keys=True).encode('utf-8')
        ).hexdigest()
        
        # Check if we already have this exact data
        existing = CounterpartySnapshot.query.filter(
            and_(
                CounterpartySnapshot.counterparty_id == counterparty.id,
                CounterpartySnapshot.check_type == check_type,
                CounterpartySnapshot.data_hash == data_hash
            )
        ).first()
        
        if existing:
            logger.info(f"Snapshot with same data hash already exists: {existing.id}")
            return existing
        
        # Create new snapshot
        snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source=result.get('source', check_type.upper()),
            check_type=check_type,
            data_hash=data_hash,
            raw_data=result,
            status=result.get('status', 'unknown'),
            response_time_ms=result.get('response_time_ms'),
            error_message=result.get('error')
        )
        
        # Process data for easier querying
        snapshot.processed_data = _process_snapshot_data(check_type, result)
        
        db.session.add(snapshot)
        db.session.flush()
        
        return snapshot
        
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        return None


def _process_snapshot_data(check_type: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process raw data into normalized format for easier querying."""
    processed = {
        'check_type': check_type,
        'status': raw_data.get('status'),
        'checked_at': raw_data.get('checked_at')
    }
    
    if check_type == 'vat':
        processed.update({
            'valid': raw_data.get('valid'),
            'company_name': raw_data.get('name'),
            'address': raw_data.get('address'),
            'vat_number': raw_data.get('vat_number')
        })
    
    elif check_type == 'lei':
        processed.update({
            'valid': raw_data.get('valid'),
            'lei_code': raw_data.get('lei_code'),
            'entity_status': raw_data.get('entity_status'),
            'legal_name': raw_data.get('legal_name'),
            'legal_form': raw_data.get('legal_form'),
            'registration_authority': raw_data.get('registration_authority'),
            'legal_address': raw_data.get('legal_address'),
            'headquarters_address': raw_data.get('headquarters_address'),
            'lei_data': raw_data.get('data', {})
        })
    
    elif check_type.startswith('sanctions'):
        processed.update({
            'matches_found': raw_data.get('match_count', 0) > 0,
            'match_count': raw_data.get('match_count', 0),
            'matches': raw_data.get('matches', [])
        })
    
    elif check_type == 'insolvency_de':
        processed.update({
            'insolvency_found': raw_data.get('insolvency_found', False)
        })
    
    return processed


def _compare_snapshots(old_snapshot: CounterpartySnapshot, 
                      new_snapshot: CounterpartySnapshot) -> List[Dict[str, Any]]:
    """Compare two snapshots and return list of changes."""
    changes = []
    
    # Compare processed data
    old_data = old_snapshot.processed_data or {}
    new_data = new_snapshot.processed_data or {}
    
    # Find changes in processed data
    for key, new_value in new_data.items():
        old_value = old_data.get(key)
        
        if old_value != new_value:
            change = {
                'field_path': key,
                'old_value': str(old_value) if old_value is not None else None,
                'new_value': str(new_value) if new_value is not None else None,
                'change_type': 'modified' if old_value is not None else 'added',
                'risk_impact': _assess_change_risk_impact(key, old_value, new_value),
                'risk_score_delta': _calculate_risk_score_delta(key, old_value, new_value)
            }
            changes.append(change)
    
    # Find removed fields
    for key, old_value in old_data.items():
        if key not in new_data:
            change = {
                'field_path': key,
                'old_value': str(old_value) if old_value is not None else None,
                'new_value': None,
                'change_type': 'removed',
                'risk_impact': _assess_change_risk_impact(key, old_value, None),
                'risk_score_delta': _calculate_risk_score_delta(key, old_value, None)
            }
            changes.append(change)
    
    return changes


def _assess_change_risk_impact(field_path: str, old_value: Any, new_value: Any) -> str:
    """Assess the risk impact of a field change."""
    # Critical risk changes
    if field_path in ['matches_found', 'insolvency_found']:
        if new_value and not old_value:
            return 'critical'
        elif old_value and not new_value:
            return 'medium'
    
    # High risk changes
    if field_path == 'valid':
        if old_value and not new_value:
            return 'high'
        elif not old_value and new_value:
            return 'low'
    
    if field_path == 'entity_status':
        if new_value in ['INACTIVE', 'LAPSED'] and old_value == 'ACTIVE':
            return 'high'
        elif new_value == 'ACTIVE' and old_value in ['INACTIVE', 'LAPSED']:
            return 'medium'
    
    # Medium risk changes
    if field_path in ['company_name', 'address', 'legal_name', 'legal_form']:
        return 'medium'
    
    # Low risk changes
    if field_path in ['registration_authority', 'legal_address', 'headquarters_address']:
        return 'low'
    
    # Default low risk
    return 'low'


def _calculate_risk_score_delta(field_path: str, old_value: Any, new_value: Any) -> float:
    """Calculate the change in risk score for a field change."""
    if field_path == 'matches_found':
        if new_value and not old_value:
            return 50.0  # Sanctions match found
        elif old_value and not new_value:
            return -50.0  # Sanctions match cleared
    
    elif field_path == 'insolvency_found':
        if new_value and not old_value:
            return 40.0  # Insolvency found
        elif old_value and not new_value:
            return -40.0  # Insolvency cleared
    
    elif field_path == 'valid':
        if old_value and not new_value:
            return 20.0  # Validation failed
        elif not old_value and new_value:
            return -20.0  # Validation restored
    
    elif field_path == 'entity_status':
        if new_value in ['INACTIVE', 'LAPSED'] and old_value == 'ACTIVE':
            return 25.0  # LEI became inactive/lapsed
        elif new_value == 'ACTIVE' and old_value in ['INACTIVE', 'LAPSED']:
            return -15.0  # LEI became active again
    
    elif field_path in ['company_name', 'address', 'legal_name']:
        return 10.0  # Significant data change
    
    elif field_path in ['legal_form', 'registration_authority']:
        return 5.0  # Minor data change
    
    elif field_path in ['legal_address', 'headquarters_address']:
        return 3.0  # Address change
    
    return 0.0


def _generate_alert_from_diff(diff: CounterpartyDiff, 
                             config: KYBMonitoringConfig) -> Optional[KYBAlert]:
    """Generate an alert from a detected change."""
    # Check if alerts are enabled for this type of change
    if not _should_generate_alert(diff, config):
        return None
    
    # Determine alert type and severity
    alert_type, severity = _determine_alert_type_and_severity(diff)
    
    # Generate alert message
    title, message = _generate_alert_message(diff)
    
    alert = KYBAlert(
        tenant_id=diff.counterparty.tenant_id,
        counterparty_id=diff.counterparty_id,
        diff_id=diff.id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        alert_data={
            'field_path': diff.field_path,
            'old_value': diff.old_value,
            'new_value': diff.new_value,
            'change_type': diff.change_type,
            'risk_impact': diff.risk_impact,
            'risk_score_delta': diff.risk_score_delta
        },
        source='KYB_MONITORING'
    )
    
    return alert


def _should_generate_alert(diff: CounterpartyDiff, config: KYBMonitoringConfig) -> bool:
    """Check if an alert should be generated for this diff."""
    if diff.field_path == 'matches_found' and diff.new_value == 'True':
        return config.alert_on_sanctions_match
    
    elif diff.field_path == 'valid' and diff.new_value == 'False':
        if 'vat' in diff.field_path.lower() or 'VIES' in (diff.old_snapshot.source if diff.old_snapshot else ''):
            return config.alert_on_vat_invalid
        elif 'lei' in diff.field_path.lower() or 'GLEIF' in (diff.old_snapshot.source if diff.old_snapshot else ''):
            return config.alert_on_lei_invalid
    
    elif diff.field_path == 'entity_status' and diff.new_value in ['INACTIVE', 'LAPSED']:
        return config.alert_on_lei_invalid  # Treat inactive/lapsed LEI as validation issue
    
    elif diff.field_path == 'insolvency_found' and diff.new_value == 'True':
        return config.alert_on_insolvency
    
    elif diff.change_type in ['added', 'modified', 'removed']:
        return config.alert_on_data_change
    
    return False


def _determine_alert_type_and_severity(diff: CounterpartyDiff) -> Tuple[str, str]:
    """Determine alert type and severity based on the diff."""
    if diff.field_path == 'matches_found' and diff.new_value == 'True':
        return 'sanctions_match', 'critical'
    
    elif diff.field_path == 'insolvency_found' and diff.new_value == 'True':
        return 'insolvency_detected', 'high'
    
    elif diff.field_path == 'valid' and diff.new_value == 'False':
        return 'validation_failure', 'medium'
    
    elif diff.change_type in ['added', 'modified', 'removed']:
        severity = 'low' if diff.risk_impact == 'low' else 'medium'
        return 'data_change', severity
    
    return 'unknown', 'low'


def _generate_alert_message(diff: CounterpartyDiff) -> Tuple[str, str]:
    """Generate alert title and message."""
    counterparty_name = diff.counterparty.name if diff.counterparty else 'Unknown'
    
    if diff.field_path == 'matches_found' and diff.new_value == 'True':
        title = f"Sanctions Match Detected: {counterparty_name}"
        message = f"A sanctions match has been detected for counterparty {counterparty_name}. Immediate review required."
    
    elif diff.field_path == 'insolvency_found' and diff.new_value == 'True':
        title = f"Insolvency Detected: {counterparty_name}"
        message = f"Insolvency proceedings detected for counterparty {counterparty_name}."
    
    elif diff.field_path == 'valid' and diff.new_value == 'False':
        title = f"Validation Failure: {counterparty_name}"
        message = f"Validation failed for counterparty {counterparty_name}. Previous status: {diff.old_value}"
    
    else:
        title = f"Data Change: {counterparty_name}"
        message = f"Data change detected for counterparty {counterparty_name}. Field: {diff.field_path}, Changed from '{diff.old_value}' to '{diff.new_value}'"
    
    return title, message


def _generate_risk_based_alerts(counterparty: Counterparty, 
                               config: KYBMonitoringConfig) -> List[KYBAlert]:
    """Generate alerts based on overall risk conditions."""
    alerts = []
    
    # Check if risk score is above threshold
    if counterparty.risk_score >= 80:  # High risk threshold
        alert = KYBAlert(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            alert_type='high_risk_score',
            severity='high',
            title=f"High Risk Score: {counterparty.name}",
            message=f"Counterparty {counterparty.name} has a high risk score of {counterparty.risk_score}",
            alert_data={
                'risk_score': counterparty.risk_score,
                'risk_level': counterparty.risk_level
            },
            source='RISK_ASSESSMENT'
        )
        alerts.append(alert)
    
    return alerts


def _update_counterparty_risk_score(counterparty: Counterparty):
    """Update counterparty risk score based on latest findings."""
    # Get latest snapshots
    latest_snapshots = CounterpartySnapshot.query.filter(
        CounterpartySnapshot.counterparty_id == counterparty.id
    ).order_by(CounterpartySnapshot.created_at.desc()).limit(10).all()
    
    risk_score = 0.0
    
    for snapshot in latest_snapshots:
        processed_data = snapshot.processed_data or {}
        
        # Sanctions matches - highest risk
        if processed_data.get('matches_found') or processed_data.get('match_count', 0) > 0:
            risk_score += 70.0  # High risk for sanctions
        
        # Insolvency
        if processed_data.get('insolvency_found'):
            risk_score += 40.0
        
        # Invalid validation
        if processed_data.get('valid') is False:
            risk_score += 20.0
    
    # Cap at 100
    counterparty.risk_score = min(risk_score, 100.0)
    counterparty.update_risk_level()


def _calculate_next_check_time(counterparty: Counterparty, 
                              config: KYBMonitoringConfig) -> datetime:
    """Calculate the next check time based on risk level and config."""
    now = datetime.utcnow()
    
    if counterparty.risk_level == 'critical':
        # Daily checks for critical risk
        return now + timedelta(days=1)
    elif counterparty.risk_level == 'high':
        # Use high risk frequency from config
        freq = config.high_risk_check_frequency
    elif counterparty.risk_level == 'low':
        # Use low risk frequency from config
        freq = config.low_risk_check_frequency
    else:
        # Use default frequency
        freq = config.default_check_frequency
    
    # Convert frequency to timedelta
    if freq == 'daily':
        return now + timedelta(days=1)
    elif freq == 'weekly':
        return now + timedelta(weeks=1)
    elif freq == 'monthly':
        return now + timedelta(days=30)
    else:
        return now + timedelta(days=1)  # Default to daily


def _create_evidence_directory(snapshot: CounterpartySnapshot) -> str:
    """Create directory structure for evidence storage."""
    base_dir = current_app.config.get('KYB_EVIDENCE_DIR', 'evidence/kyb')
    
    # Create directory structure: evidence/kyb/tenant_id/counterparty_id/year/month
    date_path = snapshot.created_at.strftime('%Y/%m')
    evidence_dir = os.path.join(
        base_dir,
        str(snapshot.counterparty.tenant_id),
        str(snapshot.counterparty_id),
        date_path
    )
    
    os.makedirs(evidence_dir, exist_ok=True)
    return evidence_dir


def _save_raw_response(snapshot: CounterpartySnapshot, evidence_dir: str) -> Optional[str]:
    """Save raw API response as evidence."""
    try:
        filename = f"raw_response_{snapshot.check_type}_{snapshot.id}.json"
        filepath = os.path.join(evidence_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot.raw_data, f, indent=2, ensure_ascii=False)
        
        return filepath
        
    except Exception as e:
        logger.error(f"Error saving raw response: {e}")
        return None


def _save_data_summary(snapshot: CounterpartySnapshot, evidence_dir: str) -> Optional[str]:
    """Save processed data summary as evidence."""
    try:
        filename = f"data_summary_{snapshot.check_type}_{snapshot.id}.json"
        filepath = os.path.join(evidence_dir, filename)
        
        summary = {
            'snapshot_id': snapshot.id,
            'counterparty_id': snapshot.counterparty_id,
            'counterparty_name': snapshot.counterparty.name,
            'check_type': snapshot.check_type,
            'source': snapshot.source,
            'status': snapshot.status,
            'checked_at': snapshot.created_at.isoformat(),
            'data_hash': snapshot.data_hash,
            'processed_data': snapshot.processed_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return filepath
        
    except Exception as e:
        logger.error(f"Error saving data summary: {e}")
        return None


def _save_compliance_report(snapshot: CounterpartySnapshot, evidence_dir: str) -> Optional[str]:
    """Save compliance report as evidence."""
    try:
        filename = f"compliance_report_{snapshot.check_type}_{snapshot.id}.txt"
        filepath = os.path.join(evidence_dir, filename)
        
        report_lines = [
            "KYB COMPLIANCE EVIDENCE REPORT",
            "=" * 50,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Snapshot ID: {snapshot.id}",
            f"Counterparty: {snapshot.counterparty.name}",
            f"Check Type: {snapshot.check_type}",
            f"Source: {snapshot.source}",
            f"Status: {snapshot.status}",
            f"Data Hash: {snapshot.data_hash}",
            "",
            "PROCESSED DATA:",
            "-" * 20
        ]
        
        if snapshot.processed_data:
            for key, value in snapshot.processed_data.items():
                report_lines.append(f"{key}: {value}")
        
        report_lines.extend([
            "",
            "RAW DATA:",
            "-" * 20,
            json.dumps(snapshot.raw_data, indent=2)
        ])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        return filepath
        
    except Exception as e:
        logger.error(f"Error saving compliance report: {e}")
        return None


# Periodic tasks for scheduling

@kyb_task
def daily_kyb_monitoring(self) -> Dict[str, Any]:
    """Daily KYB monitoring task that schedules checks for all tenants."""
    try:
        logger.info("Starting daily KYB monitoring")
        
        # Get all tenants with KYB monitoring enabled
        tenants_with_kyb = db.session.query(KYBMonitoringConfig.tenant_id).distinct().all()
        
        results = []
        
        for (tenant_id,) in tenants_with_kyb:
            try:
                result = schedule_counterparty_monitoring.apply_async(
                    args=[tenant_id],
                    countdown=0
                )
                
                results.append({
                    'tenant_id': tenant_id,
                    'task_id': result.id,
                    'scheduled_at': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error scheduling monitoring for tenant {tenant_id}: {e}")
                results.append({
                    'tenant_id': tenant_id,
                    'error': str(e)
                })
        
        summary = {
            'tenants_processed': len(tenants_with_kyb),
            'tasks_scheduled': len([r for r in results if 'error' not in r]),
            'errors': len([r for r in results if 'error' in r]),
            'results': results,
            'executed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed daily KYB monitoring: {summary['tasks_scheduled']} tenants scheduled")
        return summary
        
    except Exception as e:
        logger.error(f"Error in daily_kyb_monitoring: {e}")
        raise


@kyb_task
def cleanup_old_kyb_data(retention_days: int = None) -> Dict[str, Any]:
    """Clean up old KYB data based on retention policies."""
    try:
        logger.info("Starting KYB data cleanup")
        
        # Get default retention from config or use 365 days
        if not retention_days:
            retention_days = 365
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Clean up old snapshots
        old_snapshots = CounterpartySnapshot.query.filter(
            CounterpartySnapshot.created_at < cutoff_date
        ).all()
        
        snapshots_deleted = 0
        evidence_cleaned = 0
        
        for snapshot in old_snapshots:
            try:
                # Clean up evidence files
                if snapshot.evidence_path and os.path.exists(snapshot.evidence_path):
                    import shutil
                    shutil.rmtree(snapshot.evidence_path)
                    evidence_cleaned += 1
                
                # Delete snapshot
                db.session.delete(snapshot)
                snapshots_deleted += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up snapshot {snapshot.id}: {e}")
        
        # Clean up old alerts (keep longer for audit purposes)
        alert_retention_days = retention_days * 3  # 3x longer retention for alerts
        alert_cutoff_date = datetime.utcnow() - timedelta(days=alert_retention_days)
        
        old_alerts = KYBAlert.query.filter(
            and_(
                KYBAlert.created_at < alert_cutoff_date,
                KYBAlert.status.in_(['resolved', 'false_positive'])
            )
        ).all()
        
        alerts_deleted = 0
        for alert in old_alerts:
            try:
                db.session.delete(alert)
                alerts_deleted += 1
            except Exception as e:
                logger.error(f"Error cleaning up alert {alert.id}: {e}")
        
        db.session.commit()
        
        result = {
            'retention_days': retention_days,
            'cutoff_date': cutoff_date.isoformat(),
            'snapshots_deleted': snapshots_deleted,
            'evidence_directories_cleaned': evidence_cleaned,
            'alerts_deleted': alerts_deleted,
            'cleaned_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed KYB data cleanup: {snapshots_deleted} snapshots, {alerts_deleted} alerts deleted")
        return result
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_kyb_data: {e}")
        raise
# Sanctions Monitoring Tasks

@kyb_task
def check_counterparty_sanctions(self, counterparty_id: int, **kwargs) -> Dict[str, Any]:
    """
    Check a counterparty against all sanctions sources.
    
    Args:
        counterparty_id: Counterparty ID to check
        **kwargs: Additional options for sanctions adapters
    
    Returns:
        Dict with sanctions check results
    """
    try:
        logger.info(f"Starting sanctions check for counterparty {counterparty_id}")
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Perform comprehensive sanctions check
        result = sanctions_service.check_counterparty_sanctions(counterparty_id, **kwargs)
        
        # If matches found, schedule alert generation
        if result.get('total_matches', 0) > 0:
            generate_sanctions_alerts.apply_async(
                args=[counterparty_id, result.get('matches', [])],
                countdown=5  # Small delay to ensure snapshots are committed
            )
        
        logger.info(f"Completed sanctions check for counterparty {counterparty_id}: "
                   f"{result.get('total_matches', 0)} matches found")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in check_counterparty_sanctions: {e}")
        raise


@kyb_task
def batch_check_sanctions(self, counterparty_ids: List[int], **kwargs) -> Dict[str, Any]:
    """
    Check multiple counterparties against sanctions sources.
    
    Args:
        counterparty_ids: List of counterparty IDs to check
        **kwargs: Additional options for sanctions adapters
    
    Returns:
        Dict with batch sanctions check results
    """
    try:
        logger.info(f"Starting batch sanctions check for {len(counterparty_ids)} counterparties")
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Perform batch sanctions check
        results = sanctions_service.batch_check_counterparties(counterparty_ids, **kwargs)
        
        # Count matches and schedule alerts
        total_matches = 0
        alerts_scheduled = 0
        
        for result in results:
            matches = result.get('total_matches', 0)
            total_matches += matches
            
            if matches > 0:
                counterparty_id = result.get('counterparty_id')
                if counterparty_id:
                    generate_sanctions_alerts.apply_async(
                        args=[counterparty_id, result.get('matches', [])],
                        countdown=10  # Stagger alert generation
                    )
                    alerts_scheduled += 1
        
        batch_result = {
            'counterparty_ids': counterparty_ids,
            'total_checked': len(counterparty_ids),
            'total_matches': total_matches,
            'alerts_scheduled': alerts_scheduled,
            'results': results,
            'checked_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed batch sanctions check: {total_matches} total matches, "
                   f"{alerts_scheduled} alerts scheduled")
        
        return batch_result
        
    except Exception as e:
        logger.error(f"Error in batch_check_sanctions: {e}")
        raise


@kyb_task
def generate_sanctions_alerts(self, counterparty_id: int, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate alerts for sanctions matches.
    
    Args:
        counterparty_id: Counterparty ID
        matches: List of sanctions matches
    
    Returns:
        Dict with alert generation results
    """
    try:
        logger.info(f"Generating sanctions alerts for counterparty {counterparty_id}")
        
        # Get counterparty
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            raise ValueError(f"Counterparty {counterparty_id} not found")
        
        # Group matches by source for cleaner alerts
        matches_by_source = {}
        for match in matches:
            source = match.get('source', 'Unknown')
            if source not in matches_by_source:
                matches_by_source[source] = []
            matches_by_source[source].append(match)
        
        # Create alerts
        alerts_created = []
        
        for source, source_matches in matches_by_source.items():
            # Determine severity based on match details
            severity = 'critical'  # All sanctions matches are critical
            
            # Create alert
            alert = KYBAlert(
                tenant_id=counterparty.tenant_id,
                counterparty_id=counterparty_id,
                alert_type='sanctions_match',
                severity=severity,
                title=f'Sanctions Match Detected - {source}',
                message=f'Counterparty "{counterparty.name}" matches {len(source_matches)} '
                       f'entries in {source} sanctions list. Immediate review required.',
                alert_data={
                    'source': source,
                    'matches': source_matches,
                    'total_matches': len(source_matches),
                    'counterparty_name': counterparty.name,
                    'risk_level': 'critical',
                    'requires_immediate_action': True
                },
                source=f'SanctionsMonitor_{source}'
            )
            
            db.session.add(alert)
            db.session.flush()
            alerts_created.append(alert.id)
        
        db.session.commit()
        
        # Update counterparty status to under review
        counterparty.status = 'under_review'
        counterparty.risk_score = max(counterparty.risk_score, 95.0)
        counterparty.update_risk_level()
        db.session.commit()
        
        result = {
            'counterparty_id': counterparty_id,
            'matches_processed': len(matches),
            'alerts_created': alerts_created,
            'sources_alerted': list(matches_by_source.keys()),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Generated {len(alerts_created)} sanctions alerts for counterparty {counterparty_id}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in generate_sanctions_alerts: {e}")
        db.session.rollback()
        raise


@kyb_task
def update_sanctions_data(self) -> Dict[str, Any]:
    """
    Update sanctions data for all sources.
    
    Returns:
        Dict with update results
    """
    try:
        logger.info("Starting sanctions data update")
        
        # Initialize sanctions service
        sanctions_service = SanctionsMonitoringService()
        
        # Update all sanctions data
        result = sanctions_service.update_all_sanctions_data()
        
        logger.info("Completed sanctions data update")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in update_sanctions_data: {e}")
        raise


@kyb_task
def schedule_sanctions_monitoring(self, tenant_id: int = None) -> Dict[str, Any]:
    """
    Schedule sanctions monitoring for counterparties.
    
    Args:
        tenant_id: Optional tenant ID to limit to specific tenant
    
    Returns:
        Dict with scheduling results
    """
    try:
        logger.info("Starting sanctions monitoring scheduling")
        
        # Get counterparties that need sanctions checking
        now = datetime.utcnow()
        
        # Check counterparties that haven't been checked recently or have high risk
        query = Counterparty.query.filter(
            Counterparty.monitoring_enabled == True
        )
        
        if tenant_id:
            query = query.filter(Counterparty.tenant_id == tenant_id)
        
        # Get counterparties that need sanctions checking
        # - Haven't been checked in the last 24 hours for sanctions
        # - High risk counterparties (checked more frequently)
        # - New counterparties
        
        counterparties = query.all()
        
        # Filter based on last sanctions check
        counterparties_to_check = []
        for cp in counterparties:
            # Check if we have recent sanctions snapshots
            recent_sanctions_check = CounterpartySnapshot.query.filter(
                and_(
                    CounterpartySnapshot.counterparty_id == cp.id,
                    CounterpartySnapshot.check_type.in_(['sanctions_eu', 'sanctions_ofac', 'sanctions_uk']),
                    CounterpartySnapshot.created_at >= now - timedelta(hours=24)
                )
            ).first()
            
            # Schedule if no recent check or high risk
            if not recent_sanctions_check or cp.risk_level in ['high', 'critical']:
                counterparties_to_check.append(cp)
        
        # Schedule sanctions checks
        scheduled_tasks = []
        
        # Process in batches to avoid overwhelming the system
        batch_size = 10
        for i in range(0, len(counterparties_to_check), batch_size):
            batch = counterparties_to_check[i:i + batch_size]
            batch_ids = [cp.id for cp in batch]
            
            # Schedule batch check with staggered timing
            task = batch_check_sanctions.apply_async(
                args=[batch_ids],
                countdown=i * 30  # 30 second delay between batches
            )
            
            scheduled_tasks.append({
                'batch_number': i // batch_size + 1,
                'counterparty_ids': batch_ids,
                'task_id': task.id,
                'scheduled_for': (now + timedelta(seconds=i * 30)).isoformat()
            })
        
        result = {
            'total_counterparties': len(counterparties),
            'counterparties_to_check': len(counterparties_to_check),
            'batches_scheduled': len(scheduled_tasks),
            'scheduled_tasks': scheduled_tasks,
            'scheduled_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Scheduled sanctions monitoring for {len(counterparties_to_check)} counterparties "
                   f"in {len(scheduled_tasks)} batches")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in schedule_sanctions_monitoring: {e}")
        raise


# Update the existing _determine_check_types function to include sanctions
def _determine_check_types_with_sanctions(counterparty: Counterparty, config: KYBMonitoringConfig) -> List[str]:
    """Determine which check types to perform including sanctions checks."""
    check_types = _determine_check_types(counterparty, config)
    
    # Add sanctions checks based on configuration
    if config.sanctions_eu_enabled:
        check_types.append('sanctions_eu')
    if config.sanctions_ofac_enabled:
        check_types.append('sanctions_ofac')
    if config.sanctions_uk_enabled:
        check_types.append('sanctions_uk')
    
    return check_types


# Update the existing _perform_data_check function to handle sanctions
def _perform_sanctions_check(counterparty: Counterparty, check_type: str) -> Optional[Dict[str, Any]]:
    """Perform sanctions check for a counterparty."""
    try:
        sanctions_service = SanctionsMonitoringService()
        
        if check_type == 'sanctions_eu':
            result = sanctions_service.eu_adapter.check_single(counterparty.name)
        elif check_type == 'sanctions_ofac':
            result = sanctions_service.ofac_adapter.check_single(counterparty.name)
        elif check_type == 'sanctions_uk':
            result = sanctions_service.uk_adapter.check_single(counterparty.name)
        else:
            return None
        
        return result
        
    except Exception as e:
        logger.error(f"Error performing {check_type} check: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'source': check_type.upper(),
            'checked_at': datetime.utcnow().isoformat()
        }