"""KYB (Know Your Business) service for counterparty verification."""
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from flask import current_app
from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, CounterpartyDiff, KYBAlert
from app import db


class KYBService:
    """Service for KYB checks and monitoring."""
    
    @staticmethod
    def check_vat_number(vat_number: str, country_code: str) -> Dict:
        """Check VAT number using VIES API."""
        start_time = time.time()
        
        # Clean VAT number (remove spaces, country prefix if present)
        clean_vat = vat_number.replace(' ', '').replace('-', '').upper()
        if clean_vat.startswith(country_code):
            clean_vat = clean_vat[len(country_code):]
        
        try:
            # VIES API endpoint
            url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
            
            # SOAP request body with proper formatting
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
    <soap:Header></soap:Header>
    <soap:Body>
        <tns1:checkVat>
            <tns1:countryCode>{country_code.upper()}</tns1:countryCode>
            <tns1:vatNumber>{clean_vat}</tns1:vatNumber>
        </tns1:checkVat>
    </soap:Body>
</soap:Envelope>"""
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '',
                'User-Agent': 'AI-Secretary-KYB/1.0'
            }
            
            current_app.logger.info(f"Checking VAT: {country_code}{clean_vat}")
            
            response = requests.post(url, data=soap_body, headers=headers, timeout=15)
            response_time = int((time.time() - start_time) * 1000)
            
            current_app.logger.info(f"VIES response: {response.status_code} in {response_time}ms")
            
            if response.status_code == 200:
                content = response.text
                current_app.logger.debug(f"VIES response content: {content[:500]}...")
                
                # Check for SOAP fault first
                if 'soap:Fault' in content or 'faultstring' in content:
                    fault_msg = KYBService._extract_xml_value(content, 'faultstring') or 'SOAP fault'
                    return {
                        'status': 'error',
                        'error': f'VIES SOAP fault: {fault_msg}',
                        'response_time_ms': response_time,
                        'source': 'VIES'
                    }
                
                # Check if valid
                if 'valid>true</valid' in content:
                    # Extract company name and address
                    name = KYBService._extract_xml_value(content, 'name')
                    address = KYBService._extract_xml_value(content, 'address')
                    
                    # Clean up extracted data
                    if name:
                        name = name.replace('\n', ' ').strip()
                    if address:
                        address = address.replace('\n', ' ').strip()
                    
                    return {
                        'status': 'valid',
                        'valid': True,
                        'name': name or 'Name not available',
                        'address': address or 'Address not available',
                        'country_code': country_code.upper(),
                        'vat_number': f"{country_code.upper()}{clean_vat}",
                        'response_time_ms': response_time,
                        'source': 'VIES',
                        'checked_at': datetime.utcnow().isoformat() + 'Z'
                    }
                elif 'valid>false</valid' in content:
                    return {
                        'status': 'invalid',
                        'valid': False,
                        'error': 'VAT number not found in VIES database',
                        'country_code': country_code.upper(),
                        'vat_number': f"{country_code.upper()}{clean_vat}",
                        'response_time_ms': response_time,
                        'source': 'VIES',
                        'checked_at': datetime.utcnow().isoformat() + 'Z'
                    }
                else:
                    return {
                        'status': 'error',
                        'error': 'Unexpected VIES response format',
                        'response_time_ms': response_time,
                        'source': 'VIES'
                    }
            else:
                return {
                    'status': 'error',
                    'error': f'VIES API HTTP error: {response.status_code}',
                    'response_time_ms': response_time,
                    'source': 'VIES'
                }
                
        except requests.exceptions.Timeout:
            return {
                'status': 'error',
                'error': 'VIES API timeout (15s) - service may be overloaded',
                'response_time_ms': int((time.time() - start_time) * 1000),
                'source': 'VIES'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'error',
                'error': 'Cannot connect to VIES API - network issue',
                'response_time_ms': int((time.time() - start_time) * 1000),
                'source': 'VIES'
            }
        except Exception as e:
            current_app.logger.error(f"VIES API error: {str(e)}")
            return {
                'status': 'error',
                'error': f'VIES API error: {str(e)}',
                'response_time_ms': int((time.time() - start_time) * 1000),
                'source': 'VIES'
            }
    
    @staticmethod
    def check_lei_code(lei_code: str, **kwargs) -> Dict:
        """Check LEI code using GLEIF adapter."""
        from app.services.kyb_adapters import GLEIFAdapter
        from app import redis_client
        
        try:
            adapter = GLEIFAdapter(redis_client=redis_client)
            result = adapter.check_single(lei_code, **kwargs)
            return result
        except Exception as e:
            current_app.logger.error(f"LEI check error: {str(e)}")
            return {
                'status': 'error',
                'error': f'LEI check failed: {str(e)}',
                'source': 'GLEIF',
                'identifier': lei_code
            }
    
    @staticmethod
    def check_sanctions(company_name: str, country_code: str = None) -> List[Dict]:
        """Check company against sanctions lists."""
        matches = []
        
        # EU Sanctions List
        eu_match = KYBService._check_eu_sanctions(company_name)
        if eu_match:
            matches.append(eu_match)
        
        # OFAC Sanctions List
        ofac_match = KYBService._check_ofac_sanctions(company_name)
        if ofac_match:
            matches.append(ofac_match)
        
        # UN Sanctions List
        un_match = KYBService._check_un_sanctions(company_name)
        if un_match:
            matches.append(un_match)
        
        return matches
    
    @staticmethod
    def _check_eu_sanctions(company_name: str) -> Optional[Dict]:
        """Check EU sanctions list."""
        try:
            # EU Consolidated List API (simplified check)
            # In production, you would use the official EU API or a service like OpenSanctions
            
            # For demo purposes, check against known sanctioned entities
            sanctioned_keywords = [
                'SBERBANK', 'GAZPROM', 'ROSNEFT', 'VEB', 'ROSTEC',
                'WAGNER', 'PRIGOZHIN', 'PUTIN', 'LUKASHENKO'
            ]
            
            company_upper = company_name.upper()
            
            for keyword in sanctioned_keywords:
                if keyword in company_upper:
                    return {
                        'list': 'EU_CONSOLIDATED',
                        'type': 'fuzzy',
                        'score': 85,
                        'name': company_name,
                        'matched_keyword': keyword,
                        'source': 'EU Sanctions List',
                        'detected_at': datetime.utcnow().isoformat() + 'Z'
                    }
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"EU sanctions check error: {str(e)}")
            return None
    
    @staticmethod
    def _check_ofac_sanctions(company_name: str) -> Optional[Dict]:
        """Check OFAC sanctions list."""
        try:
            # OFAC SDN List check (simplified)
            # In production, use official OFAC API or OpenSanctions
            
            ofac_keywords = [
                'SPECIALLY DESIGNATED NATIONAL', 'SDN', 'BLOCKED',
                'IRAN', 'NORTH KOREA', 'SYRIA', 'CUBA', 'VENEZUELA'
            ]
            
            company_upper = company_name.upper()
            
            for keyword in ofac_keywords:
                if keyword in company_upper:
                    return {
                        'list': 'OFAC_SDN',
                        'type': 'keyword',
                        'score': 75,
                        'name': company_name,
                        'matched_keyword': keyword,
                        'source': 'OFAC SDN List',
                        'detected_at': datetime.utcnow().isoformat() + 'Z'
                    }
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"OFAC sanctions check error: {str(e)}")
            return None
    
    @staticmethod
    def _check_un_sanctions(company_name: str) -> Optional[Dict]:
        """Check UN sanctions list."""
        # This would integrate with UN sanctions API
        # For now, return None (no matches)
        return None
    
    @staticmethod
    def perform_full_kyb_check(counterparty_id: str) -> Dict:
        """Perform comprehensive KYB check for a counterparty."""
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            return {'error': 'Counterparty not found'}
        
        results = {
            'counterparty_id': counterparty_id,
            'checks': [],
            'overall_status': 'pending',
            'risk_level': 'low'
        }
        
        # VAT number check
        if counterparty.vat_number and counterparty.country_code:
            vat_result = KYBService.check_vat_number(
                counterparty.vat_number, 
                counterparty.country_code
            )
            
            # Save check result
            kyb_check = KYBCheck(
                counterparty_id=counterparty.id,
                check_type='vat',
                source='VIES',
                status=vat_result['status'],
                result=vat_result,
                response_time_ms=vat_result.get('response_time_ms')
            )
            db.session.add(kyb_check)
            results['checks'].append(vat_result)
        
        # LEI code check
        if counterparty.lei_code:
            lei_result = KYBService.check_lei_code(counterparty.lei_code)
            
            kyb_check = KYBCheck(
                counterparty_id=counterparty.id,
                check_type='lei',
                source='GLEIF',
                status=lei_result['status'],
                result=lei_result,
                response_time_ms=lei_result.get('response_time_ms')
            )
            db.session.add(kyb_check)
            results['checks'].append(lei_result)
        
        # Sanctions check
        sanctions_matches = KYBService.check_sanctions(
            counterparty.name, 
            counterparty.country_code
        )
        
        for match in sanctions_matches:
            # Save sanctions match
            sanctions_match = SanctionsMatch(
                counterparty_id=counterparty.id,
                sanctions_list=match['list'],
                match_type=match['type'],
                match_score=match['score'],
                matched_name=match['name'],
                matched_details=match
            )
            db.session.add(sanctions_match)
            results['checks'].append(match)
            
            # Increase risk level if sanctions match found
            results['risk_level'] = 'high'
        
        # Update counterparty
        counterparty.last_checked = datetime.utcnow()
        counterparty.risk_level = results['risk_level']
        
        # Determine overall status
        if any(check.get('status') == 'error' for check in results['checks']):
            results['overall_status'] = 'error'
        elif sanctions_matches:
            results['overall_status'] = 'high_risk'
        elif all(check.get('status') == 'valid' for check in results['checks']):
            results['overall_status'] = 'verified'
        else:
            results['overall_status'] = 'partial'
        
        db.session.commit()
        
        return results
    
    @staticmethod
    def monitor_counterparty_changes(counterparty_id: str) -> List[Dict]:
        """Monitor changes in counterparty data."""
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            return []
        
        changes = []
        
        # Re-check VAT information
        if counterparty.vat_number and counterparty.country_code:
            current_vat_info = KYBService.check_vat_number(
                counterparty.vat_number,
                counterparty.country_code
            )
            
            # Get last VAT snapshot
            last_snapshot = CounterpartySnapshot.query.filter_by(
                counterparty_id=counterparty.id,
                source='VIES',
                check_type='vat'
            ).order_by(CounterpartySnapshot.created_at.desc()).first()
            
            if last_snapshot and last_snapshot.processed_data:
                # Compare current data with last snapshot
                old_name = last_snapshot.processed_data.get('legal_name')
                new_name = current_vat_info.get('name')
                
                if old_name != new_name:
                    diff = CounterpartyDiff(
                        counterparty_id=counterparty.id,
                        old_snapshot_id=last_snapshot.id,
                        field_path='legal_name',
                        old_value=old_name,
                        new_value=new_name,
                        change_type='modified',
                        risk_impact='low'
                    )
                    db.session.add(diff)
                    changes.append(diff.to_dict())
                
                old_address = last_snapshot.processed_data.get('address')
                new_address = current_vat_info.get('address')
                
                if old_address != new_address:
                    diff = CounterpartyDiff(
                        counterparty_id=counterparty.id,
                        old_snapshot_id=last_snapshot.id,
                        field_path='address',
                        old_value=old_address,
                        new_value=new_address,
                        change_type='modified',
                        risk_impact='low'
                    )
                    db.session.add(diff)
                    changes.append(diff.to_dict())
        
        # Re-check LEI information
        if counterparty.lei_code:
            current_lei_info = KYBService.check_lei_code(counterparty.lei_code)
            
            # Get last LEI snapshot
            last_lei_snapshot = CounterpartySnapshot.query.filter_by(
                counterparty_id=counterparty.id,
                source='GLEIF',
                check_type='lei'
            ).order_by(CounterpartySnapshot.created_at.desc()).first()
            
            if last_lei_snapshot and last_lei_snapshot.processed_data:
                # Compare LEI status changes
                old_status = last_lei_snapshot.processed_data.get('entity_status')
                new_status = current_lei_info.get('entity_status')
                
                if old_status != new_status:
                    risk_impact = 'high' if new_status in ['INACTIVE', 'LAPSED'] else 'medium'
                    diff = CounterpartyDiff(
                        counterparty_id=counterparty.id,
                        old_snapshot_id=last_lei_snapshot.id,
                        field_path='entity_status',
                        old_value=old_status,
                        new_value=new_status,
                        change_type='modified',
                        risk_impact=risk_impact
                    )
                    db.session.add(diff)
                    changes.append(diff.to_dict())
                
                # Compare legal name changes
                old_lei_name = last_lei_snapshot.processed_data.get('legal_name')
                new_lei_name = current_lei_info.get('legal_name')
                
                if old_lei_name != new_lei_name:
                    diff = CounterpartyDiff(
                        counterparty_id=counterparty.id,
                        old_snapshot_id=last_lei_snapshot.id,
                        field_path='legal_name',
                        old_value=old_lei_name,
                        new_value=new_lei_name,
                        change_type='modified',
                        risk_impact='medium'
                    )
                    db.session.add(diff)
                    changes.append(diff.to_dict())
        
        db.session.commit()
        return changes
    
    @staticmethod
    def check_lei_batch(lei_codes: List[str], **kwargs) -> List[Dict]:
        """Check multiple LEI codes using GLEIF adapter."""
        from app.services.kyb_adapters import GLEIFAdapter
        from app import redis_client
        
        try:
            adapter = GLEIFAdapter(redis_client=redis_client)
            results = adapter.check_batch(lei_codes, **kwargs)
            return results
        except Exception as e:
            current_app.logger.error(f"LEI batch check error: {str(e)}")
            return [
                {
                    'status': 'error',
                    'error': f'LEI batch check failed: {str(e)}',
                    'source': 'GLEIF',
                    'identifier': lei_code
                }
                for lei_code in lei_codes
            ]
    
    @staticmethod
    def validate_lei_format(lei_code: str) -> Dict:
        """Validate LEI code format without making API call."""
        from app.services.kyb_adapters import GLEIFAdapter
        
        try:
            adapter = GLEIFAdapter()
            result = adapter.validate_lei_format(lei_code)
            return result
        except Exception as e:
            current_app.logger.error(f"LEI format validation error: {str(e)}")
            return {
                'valid': False,
                'error': f'LEI format validation failed: {str(e)}',
                'message': 'LEI code format validation error'
            }
    
    @staticmethod
    def search_lei_by_name(entity_name: str, country_code: str = None, **kwargs) -> List[Dict]:
        """Search for LEI codes by entity name."""
        from app.services.kyb_adapters import GLEIFAdapter
        from app import redis_client
        
        try:
            adapter = GLEIFAdapter(redis_client=redis_client)
            results = adapter.search_by_name(entity_name, country_code, **kwargs)
            return results
        except Exception as e:
            current_app.logger.error(f"LEI search error: {str(e)}")
            return []
    
    @staticmethod
    def get_lei_relationships(lei_code: str, **kwargs) -> Dict:
        """Get relationship information for a LEI code."""
        from app.services.kyb_adapters import GLEIFAdapter
        from app import redis_client
        
        try:
            adapter = GLEIFAdapter(redis_client=redis_client)
            result = adapter.get_lei_relationships(lei_code, **kwargs)
            return result
        except Exception as e:
            current_app.logger.error(f"LEI relationships error: {str(e)}")
            return {
                'lei_code': lei_code,
                'status': 'error',
                'error': f'LEI relationships lookup failed: {str(e)}'
            }
    
    @staticmethod
    def create_lei_snapshot(counterparty_id: str, lei_result: Dict) -> CounterpartySnapshot:
        """Create a snapshot from LEI check result."""
        import hashlib
        import json
        
        # Create data hash
        raw_data_str = json.dumps(lei_result, sort_keys=True)
        data_hash = hashlib.sha256(raw_data_str.encode()).hexdigest()
        
        # Extract processed data
        processed_data = {
            'lei_code': lei_result.get('lei_code'),
            'entity_status': lei_result.get('entity_status'),
            'legal_name': lei_result.get('legal_name'),
            'legal_form': lei_result.get('legal_form'),
            'registration_authority': lei_result.get('registration_authority'),
            'legal_address': lei_result.get('legal_address'),
            'headquarters_address': lei_result.get('headquarters_address')
        }
        
        snapshot = CounterpartySnapshot(
            counterparty_id=counterparty_id,
            source='GLEIF',
            check_type='lei',
            data_hash=data_hash,
            raw_data=lei_result,
            processed_data=processed_data,
            status=lei_result.get('status', 'unknown'),
            response_time_ms=lei_result.get('response_time_ms'),
            error_message=lei_result.get('error')
        )
        
        db.session.add(snapshot)
        return snapshot
    
    @staticmethod
    def detect_lei_changes(counterparty_id: str, new_snapshot: CounterpartySnapshot) -> List[CounterpartyDiff]:
        """Detect changes in LEI data by comparing with previous snapshot."""
        # Get the most recent previous snapshot
        previous_snapshot = CounterpartySnapshot.query.filter_by(
            counterparty_id=counterparty_id,
            source='GLEIF',
            check_type='lei'
        ).filter(
            CounterpartySnapshot.id != new_snapshot.id
        ).order_by(CounterpartySnapshot.created_at.desc()).first()
        
        if not previous_snapshot or not previous_snapshot.processed_data:
            return []
        
        diffs = []
        old_data = previous_snapshot.processed_data
        new_data = new_snapshot.processed_data
        
        # Compare key fields
        fields_to_compare = [
            ('entity_status', 'high'),  # Status changes are high risk
            ('legal_name', 'medium'),   # Name changes are medium risk
            ('legal_form', 'low'),      # Form changes are low risk
            ('registration_authority', 'low'),
            ('legal_address', 'low'),
            ('headquarters_address', 'low')
        ]
        
        for field, risk_impact in fields_to_compare:
            old_value = old_data.get(field)
            new_value = new_data.get(field)
            
            if old_value != new_value:
                change_type = 'modified' if old_value and new_value else ('added' if new_value else 'removed')
                
                diff = CounterpartyDiff(
                    counterparty_id=counterparty_id,
                    old_snapshot_id=previous_snapshot.id,
                    new_snapshot_id=new_snapshot.id,
                    field_path=field,
                    old_value=str(old_value) if old_value else None,
                    new_value=str(new_value) if new_value else None,
                    change_type=change_type,
                    risk_impact=risk_impact
                )
                
                # Calculate risk score delta based on change type and field
                if field == 'entity_status':
                    if new_value in ['INACTIVE', 'LAPSED']:
                        diff.risk_score_delta = 30.0
                    elif new_value == 'ACTIVE' and old_value in ['INACTIVE', 'LAPSED']:
                        diff.risk_score_delta = -20.0
                elif field == 'legal_name':
                    diff.risk_score_delta = 10.0
                else:
                    diff.risk_score_delta = 5.0
                
                diffs.append(diff)
                db.session.add(diff)
        
        return diffs
    
    @staticmethod
    def _extract_xml_value(xml_content: str, tag: str) -> Optional[str]:
        """Extract value from XML content."""
        start_tag = f'<{tag}>'
        end_tag = f'</{tag}>'
        
        start_index = xml_content.find(start_tag)
        if start_index == -1:
            return None
        
        start_index += len(start_tag)
        end_index = xml_content.find(end_tag, start_index)
        
        if end_index == -1:
            return None
        
        return xml_content[start_index:end_index].strip()
    
    @staticmethod
    def get_counterparty_summary(company_id: str) -> Dict:
        """Get KYB summary for a company."""
        counterparties = Counterparty.query.filter_by(company_id=company_id).all()
        
        total = len(counterparties)
        checked = len([cp for cp in counterparties if cp.last_checked])
        high_risk = len([cp for cp in counterparties if cp.risk_level == 'high'])
        
        recent_checks = KYBCheck.query.join(Counterparty).filter(
            Counterparty.company_id == company_id
        ).order_by(KYBCheck.checked_at.desc()).limit(10).all()
        
        recent_changes = ChangeMonitoring.query.join(Counterparty).filter(
            Counterparty.company_id == company_id,
            ChangeMonitoring.notified == False
        ).order_by(ChangeMonitoring.detected_at.desc()).limit(10).all()
        
        return {
            'total_counterparties': total,
            'checked_counterparties': checked,
            'pending_checks': total - checked,
            'high_risk_counterparties': high_risk,
            'recent_checks': [check.to_dict() for check in recent_checks],
            'recent_changes': [change.to_dict() for change in recent_changes]
        }