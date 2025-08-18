"""German insolvency monitoring service."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app
from app import db
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, CounterpartyDiff, KYBAlert
)
from app.services.kyb_adapters.insolvency_de import GermanInsolvencyAdapter
from app.utils.exceptions import KYBError

logger = logging.getLogger(__name__)


class InsolvencyMonitoringService:
    """Service for monitoring German insolvency proceedings."""
    
    def __init__(self, redis_client=None):
        """Initialize insolvency monitoring service."""
        self.adapter = GermanInsolvencyAdapter(redis_client)
    
    def check_counterparty_insolvency(self, counterparty_id: int) -> Dict[str, Any]:
        """
        Check a counterparty for insolvency proceedings.
        
        Args:
            counterparty_id: ID of the counterparty to check
        
        Returns:
            Dict with check results
        """
        try:
            # Get counterparty
            counterparty = Counterparty.query.get(counterparty_id)
            if not counterparty:
                raise KYBError(f"Counterparty {counterparty_id} not found")
            
            # Only check German companies
            if counterparty.country_code != 'DE':
                return {
                    'counterparty_id': counterparty_id,
                    'status': 'skipped',
                    'reason': 'not_german_company',
                    'country_code': counterparty.country_code
                }
            
            # Prepare search parameters
            search_params = {
                'registration_number': counterparty.registration_number,
                'city': counterparty.city,
                'postal_code': counterparty.postal_code
            }
            
            # Remove None values
            search_params = {k: v for k, v in search_params.items() if v}
            
            # Perform insolvency check
            result = self.adapter.check_single(counterparty.name, **search_params)
            
            # Process and store results
            processed_result = self._process_insolvency_result(counterparty, result)
            
            # Create snapshot
            snapshot = self._create_insolvency_snapshot(counterparty, processed_result)
            
            # Check for changes and generate alerts if needed
            if snapshot and processed_result.get('proceedings_found'):
                self._check_for_new_proceedings(counterparty, snapshot)
            
            return {
                'counterparty_id': counterparty_id,
                'counterparty_name': counterparty.name,
                'check_result': processed_result,
                'snapshot_id': snapshot.id if snapshot else None,
                'checked_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking insolvency for counterparty {counterparty_id}: {e}")
            raise KYBError(f"Insolvency check failed: {str(e)}")
    
    def batch_check_insolvency(self, counterparty_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Check multiple counterparties for insolvency proceedings.
        
        Args:
            counterparty_ids: List of counterparty IDs to check
        
        Returns:
            List of check results
        """
        results = []
        
        for counterparty_id in counterparty_ids:
            try:
                result = self.check_counterparty_insolvency(counterparty_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch insolvency check for {counterparty_id}: {e}")
                results.append({
                    'counterparty_id': counterparty_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def get_insolvency_summary(self, tenant_id: int) -> Dict[str, Any]:
        """
        Get insolvency monitoring summary for a tenant.
        
        Args:
            tenant_id: Tenant ID
        
        Returns:
            Dict with insolvency summary
        """
        try:
            # Get all German counterparties for the tenant
            german_counterparties = Counterparty.query.filter_by(
                tenant_id=tenant_id,
                country_code='DE'
            ).all()
            
            # Get recent insolvency snapshots
            recent_snapshots = CounterpartySnapshot.query.join(Counterparty).filter(
                Counterparty.tenant_id == tenant_id,
                CounterpartySnapshot.check_type == 'insolvency_de',
                CounterpartySnapshot.created_at >= datetime.utcnow() - timedelta(days=30)
            ).order_by(CounterpartySnapshot.created_at.desc()).limit(50).all()
            
            # Count proceedings found
            proceedings_found = 0
            active_proceedings = 0
            
            for snapshot in recent_snapshots:
                if snapshot.processed_data and snapshot.processed_data.get('proceedings_found'):
                    proceedings_found += 1
                    
                    # Check if any proceedings are active
                    proceedings = snapshot.processed_data.get('proceedings', [])
                    for proceeding in proceedings:
                        if proceeding.get('status') in ['opened', 'applied']:
                            active_proceedings += 1
                            break
            
            # Get recent alerts
            recent_alerts = KYBAlert.query.join(Counterparty).filter(
                Counterparty.tenant_id == tenant_id,
                KYBAlert.alert_type == 'insolvency_detected',
                KYBAlert.created_at >= datetime.utcnow() - timedelta(days=30)
            ).order_by(KYBAlert.created_at.desc()).limit(10).all()
            
            return {
                'tenant_id': tenant_id,
                'total_german_counterparties': len(german_counterparties),
                'recent_checks': len(recent_snapshots),
                'proceedings_found': proceedings_found,
                'active_proceedings': active_proceedings,
                'recent_alerts': len(recent_alerts),
                'alert_details': [alert.to_dict() for alert in recent_alerts],
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating insolvency summary for tenant {tenant_id}: {e}")
            raise KYBError(f"Failed to generate insolvency summary: {str(e)}")
    
    def get_proceeding_details(self, case_number: str, court: str = None) -> Dict[str, Any]:
        """
        Get detailed information about a specific insolvency proceeding.
        
        Args:
            case_number: Case number of the proceeding
            court: Optional court name
        
        Returns:
            Dict with proceeding details
        """
        try:
            return self.adapter.get_proceeding_details(case_number, court)
        except Exception as e:
            logger.error(f"Error getting proceeding details for {case_number}: {e}")
            raise KYBError(f"Failed to get proceeding details: {str(e)}")
    
    def _process_insolvency_result(self, counterparty: Counterparty, 
                                 raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw insolvency check result into standardized format.
        
        Args:
            counterparty: Counterparty object
            raw_result: Raw result from adapter
        
        Returns:
            Processed result
        """
        processed = {
            'counterparty_id': counterparty.id,
            'counterparty_name': counterparty.name,
            'country_code': counterparty.country_code,
            'check_type': 'insolvency_de',
            'status': raw_result.get('status', 'unknown'),
            'proceedings_found': raw_result.get('proceedings_found', False),
            'proceedings_count': raw_result.get('proceedings_count', 0),
            'proceedings': raw_result.get('proceedings', []),
            'search_params': raw_result.get('search_params', {}),
            'source': raw_result.get('source', 'INSOLVENCY_DE'),
            'checked_at': raw_result.get('checked_at'),
            'response_time_ms': raw_result.get('response_time_ms'),
            'error': raw_result.get('error')
        }
        
        # Analyze proceedings for risk assessment
        if processed['proceedings']:
            processed['risk_analysis'] = self._analyze_proceedings_risk(processed['proceedings'])
        
        return processed
    
    def _analyze_proceedings_risk(self, proceedings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze insolvency proceedings to assess risk level.
        
        Args:
            proceedings: List of insolvency proceedings
        
        Returns:
            Risk analysis results
        """
        risk_analysis = {
            'risk_level': 'low',
            'risk_score': 0,
            'risk_factors': [],
            'active_proceedings': 0,
            'recent_proceedings': 0
        }
        
        current_date = datetime.now()
        
        for proceeding in proceedings:
            # Check proceeding status
            status = proceeding.get('status', 'unknown')
            
            if status in ['opened', 'applied']:
                risk_analysis['active_proceedings'] += 1
                risk_analysis['risk_factors'].append(f"Active insolvency proceeding: {status}")
                risk_analysis['risk_score'] += 80  # High risk for active proceedings
            
            elif status in ['terminated', 'cancelled']:
                risk_analysis['risk_score'] += 20  # Lower risk for terminated proceedings
                risk_analysis['risk_factors'].append(f"Past insolvency proceeding: {status}")
            
            # Check proceeding date
            proceeding_date = proceeding.get('date')
            if proceeding_date:
                try:
                    proc_date = datetime.strptime(proceeding_date, '%Y-%m-%d')
                    days_ago = (current_date - proc_date).days
                    
                    if days_ago <= 365:  # Within last year
                        risk_analysis['recent_proceedings'] += 1
                        risk_analysis['risk_score'] += 30
                        risk_analysis['risk_factors'].append("Recent insolvency proceeding")
                except ValueError:
                    pass  # Invalid date format
        
        # Determine risk level based on score
        if risk_analysis['risk_score'] >= 80:
            risk_analysis['risk_level'] = 'critical'
        elif risk_analysis['risk_score'] >= 50:
            risk_analysis['risk_level'] = 'high'
        elif risk_analysis['risk_score'] >= 20:
            risk_analysis['risk_level'] = 'medium'
        else:
            risk_analysis['risk_level'] = 'low'
        
        return risk_analysis
    
    def _create_insolvency_snapshot(self, counterparty: Counterparty, 
                                  result: Dict[str, Any]) -> Optional[CounterpartySnapshot]:
        """
        Create a snapshot record for insolvency check result.
        
        Args:
            counterparty: Counterparty object
            result: Processed insolvency check result
        
        Returns:
            Created snapshot or None if creation failed
        """
        try:
            import hashlib
            import json
            
            # Calculate data hash
            data_hash = hashlib.sha256(
                json.dumps(result, sort_keys=True).encode('utf-8')
            ).hexdigest()
            
            # Check if we already have this exact data
            existing = CounterpartySnapshot.query.filter_by(
                counterparty_id=counterparty.id,
                check_type='insolvency_de',
                data_hash=data_hash
            ).first()
            
            if existing:
                logger.info(f"Insolvency snapshot with same data already exists: {existing.id}")
                return existing
            
            # Create new snapshot
            snapshot = CounterpartySnapshot(
                tenant_id=counterparty.tenant_id,
                counterparty_id=counterparty.id,
                source=result.get('source', 'INSOLVENCY_DE'),
                check_type='insolvency_de',
                data_hash=data_hash,
                raw_data=result,
                processed_data=result,
                status=result.get('status', 'unknown'),
                response_time_ms=result.get('response_time_ms'),
                error_message=result.get('error')
            )
            
            db.session.add(snapshot)
            db.session.commit()
            
            logger.info(f"Created insolvency snapshot {snapshot.id} for counterparty {counterparty.id}")
            return snapshot
            
        except Exception as e:
            logger.error(f"Error creating insolvency snapshot: {e}")
            db.session.rollback()
            return None
    
    def _check_for_new_proceedings(self, counterparty: Counterparty, 
                                 new_snapshot: CounterpartySnapshot) -> None:
        """
        Check for new insolvency proceedings and generate alerts.
        
        Args:
            counterparty: Counterparty object
            new_snapshot: New snapshot with insolvency data
        """
        try:
            # Get previous insolvency snapshot
            previous_snapshot = CounterpartySnapshot.query.filter(
                CounterpartySnapshot.counterparty_id == counterparty.id,
                CounterpartySnapshot.check_type == 'insolvency_de',
                CounterpartySnapshot.id != new_snapshot.id
            ).order_by(CounterpartySnapshot.created_at.desc()).first()
            
            if not previous_snapshot:
                # First time checking - generate alert if proceedings found
                if new_snapshot.processed_data.get('proceedings_found'):
                    self._generate_insolvency_alert(
                        counterparty, 
                        new_snapshot, 
                        'new_insolvency_detected',
                        'New insolvency proceedings detected'
                    )
                return
            
            # Compare proceedings
            old_proceedings = previous_snapshot.processed_data.get('proceedings', [])
            new_proceedings = new_snapshot.processed_data.get('proceedings', [])
            
            # Check for new proceedings
            old_case_numbers = {p.get('case_number') for p in old_proceedings if p.get('case_number')}
            new_case_numbers = {p.get('case_number') for p in new_proceedings if p.get('case_number')}
            
            truly_new_cases = new_case_numbers - old_case_numbers
            
            if truly_new_cases:
                self._generate_insolvency_alert(
                    counterparty,
                    new_snapshot,
                    'new_insolvency_proceeding',
                    f'New insolvency proceeding(s) detected: {", ".join(truly_new_cases)}'
                )
            
            # Check for status changes in existing proceedings
            for new_proc in new_proceedings:
                case_number = new_proc.get('case_number')
                if not case_number:
                    continue
                
                # Find corresponding old proceeding
                old_proc = next((p for p in old_proceedings if p.get('case_number') == case_number), None)
                
                if old_proc and old_proc.get('status') != new_proc.get('status'):
                    self._generate_insolvency_alert(
                        counterparty,
                        new_snapshot,
                        'insolvency_status_change',
                        f'Insolvency proceeding status changed: {case_number} from {old_proc.get("status")} to {new_proc.get("status")}'
                    )
            
        except Exception as e:
            logger.error(f"Error checking for new proceedings: {e}")
    
    def _generate_insolvency_alert(self, counterparty: Counterparty, 
                                 snapshot: CounterpartySnapshot,
                                 alert_type: str, message: str) -> None:
        """
        Generate an insolvency-related alert.
        
        Args:
            counterparty: Counterparty object
            snapshot: Related snapshot
            alert_type: Type of alert
            message: Alert message
        """
        try:
            # Determine severity based on alert type
            severity_map = {
                'new_insolvency_detected': 'high',
                'new_insolvency_proceeding': 'high',
                'insolvency_status_change': 'medium'
            }
            
            severity = severity_map.get(alert_type, 'medium')
            
            alert = KYBAlert(
                tenant_id=counterparty.tenant_id,
                counterparty_id=counterparty.id,
                alert_type='insolvency_detected',
                severity=severity,
                title=f"Insolvency Alert: {counterparty.name}",
                message=message,
                alert_data={
                    'snapshot_id': snapshot.id,
                    'alert_subtype': alert_type,
                    'proceedings_count': snapshot.processed_data.get('proceedings_count', 0),
                    'risk_analysis': snapshot.processed_data.get('risk_analysis', {})
                },
                source='INSOLVENCY_MONITORING'
            )
            
            db.session.add(alert)
            db.session.commit()
            
            logger.info(f"Generated insolvency alert {alert.id} for counterparty {counterparty.id}")
            
        except Exception as e:
            logger.error(f"Error generating insolvency alert: {e}")
            db.session.rollback()