"""Sanctions monitoring service for KYB compliance."""
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from flask import current_app
from redis import Redis
import structlog

from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, CounterpartyDiff, KYBAlert, KYBMonitoringConfig
from app.services.kyb_adapters import EUSanctionsAdapter, OFACSanctionsAdapter, UKSanctionsAdapter
from app.services.kyb_adapters.base import DataSourceUnavailable, RateLimitExceeded, ValidationError
from app import db

logger = structlog.get_logger()


class SanctionsMonitoringService:
    """Service for comprehensive sanctions monitoring across multiple jurisdictions."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize sanctions monitoring service."""
        self.redis_client = redis_client
        
        # Initialize adapters
        self.eu_adapter = EUSanctionsAdapter(redis_client)
        self.ofac_adapter = OFACSanctionsAdapter(redis_client)
        self.uk_adapter = UKSanctionsAdapter(redis_client)
        
        # Adapter mapping
        self.adapters = {
            'EU': self.eu_adapter,
            'OFAC': self.ofac_adapter,
            'UK': self.uk_adapter
        }
        
        logger.info("Sanctions monitoring service initialized", 
                   adapters=list(self.adapters.keys()))
    
    def check_entity_all_sources(self, entity_name: str, tenant_id: int, 
                                counterparty_id: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Check entity against all sanctions sources and store results.
        
        Args:
            entity_name: Entity name to check
            tenant_id: Tenant ID for data isolation
            counterparty_id: Optional counterparty ID to link results
            **kwargs: Additional options for adapters
            
        Returns:
            Comprehensive sanctions check results
        """
        start_time = time.time()
        
        try:
            logger.info("Starting comprehensive sanctions check", 
                       entity_name=entity_name, tenant_id=tenant_id)
            
            # Get tenant configuration
            config = self._get_tenant_config(tenant_id)
            
            # Determine which sources to check based on configuration
            sources_to_check = self._get_enabled_sources(config)
            
            if not sources_to_check:
                logger.warning("No sanctions sources enabled for tenant", tenant_id=tenant_id)
                return {
                    'entity_name': entity_name,
                    'status': 'skipped',
                    'message': 'No sanctions sources enabled',
                    'sources_checked': [],
                    'total_matches': 0,
                    'matches': [],
                    'response_time_ms': int((time.time() - start_time) * 1000)
                }
            
            # Check each enabled source
            all_results = {}
            all_matches = []
            total_errors = 0
            
            for source_name in sources_to_check:
                try:
                    adapter = self.adapters[source_name]
                    result = adapter.check_single(entity_name, **kwargs)
                    all_results[source_name] = result
                    
                    # Collect matches
                    if result.get('status') == 'match' and result.get('matches'):
                        for match in result['matches']:
                            match['source'] = source_name
                            all_matches.append(match)
                    
                    # Store snapshot if counterparty provided
                    if counterparty_id:
                        self._store_sanctions_snapshot(
                            counterparty_id, source_name, result, tenant_id
                        )
                    
                except Exception as e:
                    logger.error(f"Error checking {source_name} sanctions", 
                               entity_name=entity_name, error=str(e))
                    all_results[source_name] = {
                        'status': 'error',
                        'error': str(e),
                        'source': source_name
                    }
                    total_errors += 1
            
            # Analyze overall results
            overall_status = self._determine_overall_status(all_results, all_matches)
            risk_level = self._calculate_risk_level(all_matches)
            
            # Generate alerts if matches found
            alerts_generated = []
            if all_matches and counterparty_id:
                alerts_generated = self._generate_sanctions_alerts(
                    counterparty_id, all_matches, tenant_id
                )
            
            # Compile final result
            final_result = {
                'entity_name': entity_name,
                'status': overall_status,
                'risk_level': risk_level,
                'message': self._generate_summary_message(all_matches, total_errors),
                'sources_checked': list(sources_to_check),
                'sources_results': all_results,
                'total_matches': len(all_matches),
                'matches': all_matches,
                'alerts_generated': len(alerts_generated),
                'response_time_ms': int((time.time() - start_time) * 1000),
                'checked_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            logger.info("Comprehensive sanctions check completed",
                       entity_name=entity_name,
                       status=overall_status,
                       total_matches=len(all_matches),
                       sources_checked=len(sources_to_check),
                       alerts_generated=len(alerts_generated))
            
            return final_result
            
        except Exception as e:
            logger.error("Comprehensive sanctions check failed", 
                        entity_name=entity_name, error=str(e), exc_info=True)
            return {
                'entity_name': entity_name,
                'status': 'error',
                'error': str(e),
                'response_time_ms': int((time.time() - start_time) * 1000)
            }
    
    def check_counterparty_sanctions(self, counterparty_id: int, **kwargs) -> Dict[str, Any]:
        """
        Check counterparty against all sanctions sources.
        
        Args:
            counterparty_id: Counterparty ID to check
            **kwargs: Additional options for adapters
            
        Returns:
            Sanctions check results for counterparty
        """
        try:
            # Get counterparty
            counterparty = Counterparty.query.get(counterparty_id)
            if not counterparty:
                raise ValueError(f"Counterparty {counterparty_id} not found")
            
            # Check sanctions using counterparty name
            result = self.check_entity_all_sources(
                counterparty.name,
                counterparty.tenant_id,
                counterparty_id,
                **kwargs
            )
            
            # Update counterparty risk score if matches found
            if result.get('total_matches', 0) > 0:
                self._update_counterparty_risk(counterparty, result)
            
            return result
            
        except Exception as e:
            logger.error("Counterparty sanctions check failed", 
                        counterparty_id=counterparty_id, error=str(e), exc_info=True)
            raise
    
    def batch_check_counterparties(self, counterparty_ids: List[int], **kwargs) -> List[Dict[str, Any]]:
        """
        Check multiple counterparties against sanctions sources.
        
        Args:
            counterparty_ids: List of counterparty IDs to check
            **kwargs: Additional options for adapters
            
        Returns:
            List of sanctions check results
        """
        logger.info("Starting batch sanctions check", count=len(counterparty_ids))
        
        results = []
        for counterparty_id in counterparty_ids:
            try:
                result = self.check_counterparty_sanctions(counterparty_id, **kwargs)
                results.append(result)
                
                # Small delay between checks to be respectful to APIs
                time.sleep(0.5)
                
            except Exception as e:
                logger.error("Batch check failed for counterparty", 
                           counterparty_id=counterparty_id, error=str(e))
                results.append({
                    'counterparty_id': counterparty_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        logger.info("Batch sanctions check completed", 
                   total=len(counterparty_ids),
                   successful=len([r for r in results if r.get('status') != 'error']))
        
        return results
    
    def update_all_sanctions_data(self) -> Dict[str, Any]:
        """Update sanctions data for all adapters."""
        logger.info("Updating all sanctions data sources")
        
        results = {}
        for source_name, adapter in self.adapters.items():
            try:
                result = adapter.update_sanctions_data()
                results[source_name] = result
                logger.info(f"{source_name} sanctions data update completed", 
                           success=result.get('success', False))
            except Exception as e:
                logger.error(f"Failed to update {source_name} sanctions data", error=str(e))
                results[source_name] = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'sources_updated': list(results.keys()),
            'results': results,
            'updated_at': datetime.utcnow().isoformat() + 'Z'
        }
    
    def get_sanctions_statistics(self, tenant_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get sanctions monitoring statistics for a tenant.
        
        Args:
            tenant_id: Tenant ID
            days: Number of days to look back
            
        Returns:
            Statistics about sanctions monitoring
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get sanctions-related snapshots
            sanctions_snapshots = CounterpartySnapshot.query.filter(
                CounterpartySnapshot.tenant_id == tenant_id,
                CounterpartySnapshot.check_type.in_(['sanctions_eu', 'sanctions_ofac', 'sanctions_uk']),
                CounterpartySnapshot.created_at >= since_date
            ).all()
            
            # Get sanctions-related alerts
            sanctions_alerts = KYBAlert.query.filter(
                KYBAlert.tenant_id == tenant_id,
                KYBAlert.alert_type == 'sanctions_match',
                KYBAlert.created_at >= since_date
            ).all()
            
            # Analyze results
            total_checks = len(sanctions_snapshots)
            matches_found = len([s for s in sanctions_snapshots if s.status == 'match'])
            alerts_generated = len(sanctions_alerts)
            
            # Group by source
            by_source = {}
            for snapshot in sanctions_snapshots:
                source = snapshot.source
                if source not in by_source:
                    by_source[source] = {'total': 0, 'matches': 0}
                by_source[source]['total'] += 1
                if snapshot.status == 'match':
                    by_source[source]['matches'] += 1
            
            # Alert status breakdown
            alert_status_counts = {}
            for alert in sanctions_alerts:
                status = alert.status
                alert_status_counts[status] = alert_status_counts.get(status, 0) + 1
            
            return {
                'period_days': days,
                'total_sanctions_checks': total_checks,
                'matches_found': matches_found,
                'match_rate': matches_found / total_checks if total_checks > 0 else 0,
                'alerts_generated': alerts_generated,
                'by_source': by_source,
                'alert_status_breakdown': alert_status_counts,
                'generated_at': datetime.utcnow().isoformat() + 'Z'
            }
            
        except Exception as e:
            logger.error("Failed to generate sanctions statistics", 
                        tenant_id=tenant_id, error=str(e), exc_info=True)
            return {
                'error': str(e),
                'generated_at': datetime.utcnow().isoformat() + 'Z'
            }
    
    def _get_tenant_config(self, tenant_id: int) -> KYBMonitoringConfig:
        """Get or create tenant KYB monitoring configuration."""
        config = KYBMonitoringConfig.query.filter_by(tenant_id=tenant_id).first()
        if not config:
            # Create default configuration
            config = KYBMonitoringConfig(tenant_id=tenant_id)
            db.session.add(config)
            db.session.commit()
            logger.info("Created default KYB monitoring config", tenant_id=tenant_id)
        return config
    
    def _get_enabled_sources(self, config: KYBMonitoringConfig) -> List[str]:
        """Get list of enabled sanctions sources based on configuration."""
        enabled_sources = []
        
        if config.sanctions_eu_enabled:
            enabled_sources.append('EU')
        if config.sanctions_ofac_enabled:
            enabled_sources.append('OFAC')
        if config.sanctions_uk_enabled:
            enabled_sources.append('UK')
        
        return enabled_sources
    
    def _store_sanctions_snapshot(self, counterparty_id: int, source: str, 
                                 result: Dict[str, Any], tenant_id: int) -> CounterpartySnapshot:
        """Store sanctions check result as a snapshot."""
        try:
            # Determine check type based on source
            check_type_map = {
                'EU': 'sanctions_eu',
                'OFAC': 'sanctions_ofac',
                'UK': 'sanctions_uk'
            }
            check_type = check_type_map.get(source, 'sanctions')
            
            # Create snapshot
            snapshot = CounterpartySnapshot(
                tenant_id=tenant_id,
                counterparty_id=counterparty_id,
                source=source,
                check_type=check_type,
                data_hash=self._calculate_data_hash(result),
                raw_data=result,
                processed_data={
                    'matches': result.get('matches', []),
                    'total_matches': result.get('total_matches', 0),
                    'risk_level': result.get('risk_level', 'low')
                },
                status=result.get('status', 'unknown'),
                response_time_ms=result.get('response_time_ms', 0)
            )
            
            db.session.add(snapshot)
            db.session.commit()
            
            logger.debug("Sanctions snapshot stored", 
                        counterparty_id=counterparty_id, 
                        source=source,
                        status=snapshot.status)
            
            return snapshot
            
        except Exception as e:
            logger.error("Failed to store sanctions snapshot", 
                        counterparty_id=counterparty_id, 
                        source=source, 
                        error=str(e))
            db.session.rollback()
            raise
    
    def _generate_sanctions_alerts(self, counterparty_id: int, matches: List[Dict[str, Any]], 
                                  tenant_id: int) -> List[KYBAlert]:
        """Generate alerts for sanctions matches."""
        alerts = []
        
        try:
            # Get counterparty for alert context
            counterparty = Counterparty.query.get(counterparty_id)
            if not counterparty:
                return alerts
            
            # Group matches by source for cleaner alerts
            matches_by_source = {}
            for match in matches:
                source = match.get('source', 'Unknown')
                if source not in matches_by_source:
                    matches_by_source[source] = []
                matches_by_source[source].append(match)
            
            # Create alert for each source with matches
            for source, source_matches in matches_by_source.items():
                alert = KYBAlert(
                    tenant_id=tenant_id,
                    counterparty_id=counterparty_id,
                    alert_type='sanctions_match',
                    severity='critical',
                    title=f'Sanctions Match Found - {source}',
                    message=f'Counterparty "{counterparty.name}" matches {len(source_matches)} entries in {source} sanctions list',
                    alert_data={
                        'source': source,
                        'matches': source_matches,
                        'total_matches': len(source_matches),
                        'counterparty_name': counterparty.name
                    },
                    source=f'SanctionsMonitor_{source}'
                )
                
                db.session.add(alert)
                alerts.append(alert)
            
            db.session.commit()
            
            logger.info("Sanctions alerts generated", 
                       counterparty_id=counterparty_id,
                       alerts_count=len(alerts))
            
            return alerts
            
        except Exception as e:
            logger.error("Failed to generate sanctions alerts", 
                        counterparty_id=counterparty_id, error=str(e))
            db.session.rollback()
            return []
    
    def _update_counterparty_risk(self, counterparty: Counterparty, result: Dict[str, Any]) -> None:
        """Update counterparty risk score based on sanctions matches."""
        try:
            # Calculate risk score based on matches
            matches = result.get('matches', [])
            if not matches:
                return
            
            # High risk for any sanctions match
            new_risk_score = 95.0  # Critical risk for sanctions matches
            
            if counterparty.risk_score < new_risk_score:
                counterparty.risk_score = new_risk_score
                counterparty.update_risk_level()
                counterparty.status = 'under_review'  # Flag for manual review
                
                db.session.commit()
                
                logger.info("Counterparty risk updated due to sanctions match",
                           counterparty_id=counterparty.id,
                           new_risk_score=new_risk_score,
                           matches_count=len(matches))
            
        except Exception as e:
            logger.error("Failed to update counterparty risk", 
                        counterparty_id=counterparty.id, error=str(e))
            db.session.rollback()
    
    def _determine_overall_status(self, all_results: Dict[str, Dict], matches: List[Dict]) -> str:
        """Determine overall status from all source results."""
        if matches:
            return 'match'
        
        # Check if all sources had errors
        error_count = sum(1 for result in all_results.values() if result.get('status') == 'error')
        if error_count == len(all_results):
            return 'error'
        
        # Check if any sources were unavailable
        unavailable_count = sum(1 for result in all_results.values() if result.get('status') == 'unavailable')
        if unavailable_count > 0:
            return 'partial'
        
        return 'no_match'
    
    def _calculate_risk_level(self, matches: List[Dict]) -> str:
        """Calculate risk level based on matches."""
        if not matches:
            return 'low'
        
        # Any sanctions match is critical risk
        return 'critical'
    
    def _generate_summary_message(self, matches: List[Dict], error_count: int) -> str:
        """Generate summary message for the check results."""
        if matches:
            sources = set(match.get('source', 'Unknown') for match in matches)
            return f"Found {len(matches)} sanctions match(es) across {len(sources)} source(s)"
        elif error_count > 0:
            return f"Completed with {error_count} source error(s)"
        else:
            return "No sanctions matches found"
    
    def _calculate_data_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash of data for change detection."""
        import hashlib
        import json
        
        # Create a stable string representation
        stable_data = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(stable_data.encode()).hexdigest()
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Get statistics for all sanctions adapters."""
        stats = {}
        for source_name, adapter in self.adapters.items():
            try:
                stats[source_name] = adapter.get_stats()
            except Exception as e:
                stats[source_name] = {'error': str(e)}
        
        return {
            'adapters': stats,
            'total_adapters': len(self.adapters),
            'generated_at': datetime.utcnow().isoformat() + 'Z'
        }