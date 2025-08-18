"""Enhanced orchestration service for agent coordination and performance monitoring."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from app.secretary.agents.orchestrator import AgentOrchestrator, ConversationContext, AgentPerformanceMetrics
from app.secretary.agents.base_agent import AgentContext, AgentResponse


@dataclass
class OrchestrationMetrics:
    """Comprehensive orchestration metrics."""
    total_conversations: int = 0
    active_conversations: int = 0
    total_handoffs: int = 0
    successful_handoffs: int = 0
    failed_handoffs: int = 0
    average_conversation_length: float = 0.0
    average_escalation_level: float = 0.0
    agent_utilization: Dict[str, float] = None
    
    def __post_init__(self):
        if self.agent_utilization is None:
            self.agent_utilization = {}


class OrchestrationService:
    """Enhanced orchestration service with advanced coordination and monitoring."""
    
    def __init__(self):
        self.logger = logging.getLogger("orchestration.service")
        self.orchestrator = AgentOrchestrator()
        self._start_time = datetime.now()
        
        # Enhanced metrics
        self.orchestration_metrics = OrchestrationMetrics()
        self.conversation_analytics = {}
        
        # Configuration
        self.max_escalation_level = 3
        self.context_cleanup_interval = 3600  # 1 hour
        self.last_cleanup = datetime.now()
    
    async def process_message_with_coordination(self, message: str, context: AgentContext) -> AgentResponse:
        """Process message with enhanced coordination and monitoring."""
        start_time = datetime.now()
        
        try:
            # Update orchestration metrics
            self._update_orchestration_metrics(context)
            
            # Process through orchestrator
            response = await self.orchestrator.process_message(message, context)
            
            # Track conversation analytics
            await self._track_conversation_analytics(context, response, start_time)
            
            # Perform periodic cleanup
            await self._periodic_cleanup()
            
            return response
            
        except Exception as e:
            self.logger.error(f"Orchestration service error: {str(e)}", exc_info=True)
            
            # Return fallback response
            return AgentResponse(
                content="I apologize, but I'm experiencing technical difficulties. Let me connect you with a human agent who can assist you.",
                confidence=0.0,
                intent='error',
                requires_handoff=True,
                metadata={
                    'orchestration_error': True,
                    'error': str(e),
                    'fallback_response': True
                }
            )
    
    async def coordinate_agent_handoff(self, conversation_id: str, from_agent: str, 
                                     to_agent: str, reason: str, context: Dict[str, Any] = None) -> bool:
        """Coordinate agent handoff with enhanced context transfer."""
        try:
            self.logger.info(f"Coordinating handoff: {from_agent} -> {to_agent} for {conversation_id}")
            
            # Get current conversation context
            conv_context = self.orchestrator.get_conversation_context(conversation_id)
            if not conv_context:
                self.logger.warning(f"No conversation context found for {conversation_id}")
                return False
            
            # Prepare handoff context
            handoff_context = {
                'from_agent': from_agent,
                'to_agent': to_agent,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'conversation_summary': self._generate_conversation_summary(conv_context),
                'customer_context': conv_context.get('customer_profile', {}),
                'escalation_level': conv_context.get('escalation_level', 0),
                'additional_context': context or {}
            }
            
            # Perform the handoff
            success = await self.orchestrator.force_agent_handoff(
                conversation_id, to_agent, reason
            )
            
            if success:
                # Update handoff metrics
                self.orchestration_metrics.total_handoffs += 1
                self.orchestration_metrics.successful_handoffs += 1
                
                # Store handoff analytics
                await self._store_handoff_analytics(conversation_id, handoff_context)
                
                self.logger.info(f"Handoff successful: {from_agent} -> {to_agent}")
            else:
                self.orchestration_metrics.failed_handoffs += 1
                self.logger.error(f"Handoff failed: {from_agent} -> {to_agent}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Handoff coordination failed: {str(e)}")
            self.orchestration_metrics.failed_handoffs += 1
            return False
    
    async def monitor_agent_performance(self) -> Dict[str, Any]:
        """Monitor and analyze agent performance with detailed metrics."""
        try:
            # Get base analytics from orchestrator
            base_analytics = await self.orchestrator.get_agent_analytics()
            
            # Get health status
            health_status = self.orchestrator.get_agent_health_status()
            
            # Calculate enhanced metrics
            enhanced_metrics = await self._calculate_enhanced_metrics()
            
            # Get conversation analytics
            conversation_metrics = await self._get_conversation_metrics()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'uptime_hours': (datetime.now() - self._start_time).total_seconds() / 3600,
                'base_analytics': base_analytics,
                'health_status': health_status,
                'enhanced_metrics': enhanced_metrics,
                'conversation_metrics': conversation_metrics,
                'orchestration_metrics': asdict(self.orchestration_metrics),
                'system_status': self._get_system_status()
            }
            
        except Exception as e:
            self.logger.error(f"Performance monitoring failed: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def optimize_agent_routing(self, conversation_id: str) -> Dict[str, Any]:
        """Optimize agent routing based on conversation history and performance."""
        try:
            # Get conversation analytics
            conv_analytics = await self.orchestrator.get_conversation_analytics(conversation_id)
            if not conv_analytics:
                return {'error': 'Conversation not found'}
            
            # Get agent performance data
            performance_data = self.orchestrator.performance_metrics
            
            # Calculate optimal routing
            routing_recommendations = self._calculate_optimal_routing(
                conv_analytics, performance_data
            )
            
            return {
                'conversation_id': conversation_id,
                'current_agent': conv_analytics.get('current_intent'),
                'escalation_level': conv_analytics.get('escalation_level', 0),
                'routing_recommendations': routing_recommendations,
                'optimization_score': self._calculate_optimization_score(conv_analytics),
                'suggested_actions': self._get_suggested_actions(conv_analytics)
            }
            
        except Exception as e:
            self.logger.error(f"Routing optimization failed: {str(e)}")
            return {'error': str(e)}
    
    async def generate_orchestration_report(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive orchestration report."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_range_hours)
            
            # Get performance data
            performance_data = await self.monitor_agent_performance()
            
            # Calculate report metrics
            report_metrics = {
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'hours': time_range_hours
                },
                'summary': {
                    'total_conversations': self.orchestration_metrics.total_conversations,
                    'active_conversations': self.orchestration_metrics.active_conversations,
                    'total_handoffs': self.orchestration_metrics.total_handoffs,
                    'handoff_success_rate': (
                        self.orchestration_metrics.successful_handoffs / 
                        max(self.orchestration_metrics.total_handoffs, 1)
                    ),
                    'average_escalation_level': self.orchestration_metrics.average_escalation_level
                },
                'agent_performance': performance_data.get('base_analytics', {}),
                'health_status': performance_data.get('health_status', {}),
                'recommendations': await self._generate_recommendations(),
                'alerts': await self._generate_alerts()
            }
            
            return report_metrics
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {str(e)}")
            return {'error': str(e)}
    
    def _update_orchestration_metrics(self, context: AgentContext):
        """Update orchestration-level metrics."""
        if context.conversation_id:
            if context.conversation_id not in self.conversation_analytics:
                self.orchestration_metrics.total_conversations += 1
                self.conversation_analytics[context.conversation_id] = {
                    'start_time': datetime.now(),
                    'message_count': 0,
                    'agent_switches': 0,
                    'escalation_level': 0
                }
            
            # Update active conversations count
            active_count = len([
                conv for conv in self.conversation_analytics.values()
                if (datetime.now() - conv['start_time']).total_seconds() < 3600  # Active in last hour
            ])
            self.orchestration_metrics.active_conversations = active_count
    
    async def _track_conversation_analytics(self, context: AgentContext, 
                                          response: AgentResponse, start_time: datetime)elf.converin sersation_id    if conv
     is.""" analysr laternalytics fof aore handofSt      """Any]):
  : Dict[str, textandoff_conid: str, hn_ conversatioics(self,analyt_handoff_c def _store
    asynts)
    ary_pmmar".join(sureturn " |     
         nt}")
   ntee}: {co"{rolpend(fry_parts.ap       summaages
      messcate longun# Tr0]  10', '')[:ontentg.get('ctent = ms        con
    n')'unknow', 'rolee = msg.get(rol          
  ssages:n recent_me msg i     for   ts = []
ary_par        summ 
     story
  lse hi) > 5 eorystn(hi5:] if le= history[-s sagemes    recent_
     messageslast few      # Get      
  "
   le.ailab avtion historyersanvo coeturn "N     r  ory:
     ot hist  if n      , [])
y'n_histortiosaconverxt.get('onv_contetory = chis       """
 ontext.r handoff cation foconversf the  summary oate a"""Gener    
    tr:, Any]) -> sct[strtext: Di conv_con(self,ry_summaationrate_convers_gene    def ")
    
alyticsversation anexpired cons)} ion_conversat(expired{leneaned up "Clfo(fer.in self.logg           w
 = nost_cleanupelf.la     s     
             
 conv_id]alytics[on_anonversati  del self.c            
  ersations:convin expired_id nv_ for co               
   
     _id)nvs.append(cotioned_conversa       expir      
       24 hours 86400:  # conds() >.total_se'])timeart_s['st - analytic  if (now             
 items():_analytics.versationn self.con iticslyid, anaonv_ c for           ]
 = [ionsed_conversatexpir            nalytics
on a conversatiean up old      # Cl
                 )
 contexts(up_expired_r.cleanorchestratoait self.      aw    ontexts
  rsation cpired convelean up ex        # C
    p_interval:anutext_cleelf.con() > snds.total_secoeanup)cl.last_(now - self       if 
 e.now()w = datetim       no."""
  dataxpiredf e oeanup periodic clorm"Perf  ""    f):
  _cleanup(selef _periodicnc d  asy   
  ]
 l'alation_leveta['escada.metonseel'] = respn_levalatioscytics['e     analta:
       .metadasen respon iion_level'at'escaltadata and .mensespo      if reta
  from metadan scalatiock e      # Tra       
  t)
 intennse.add(respoed'].agents_us analytics['      
     ent:onse.int if resp         
   dence)
   finse.conspod(reores'].appendence_scics['confi     analyt:
       dencee.confi respons    if   
        econds())
 e).total_s_tim - startow()time.n(date.append(nse_times']po['resnalytics a
        1nt'] +=_cougeytics['messaanal]
        tics[conv_id_analyionlf.conversat = selyticsana 
         }
                []
  res': ce_scofiden 'con            
   imes': [],esponse_t       'r      t(),
   d': seuse   'agents_         0,
     tion_level':cala      'es         s': 0,
 switchet_      'agen        : 0,
  age_count'  'mess            
  e,rt_timta sstart_time':         '        {
nv_id] =s[coanalyticersation_.conv    self       :
 nalytics_aconversationot in self.if conv_id n
        ersation_idt.convcontex=    conv_id        
turn
         re         ion_id:
ersatnvxt.coif not conte     
   """ analytics.conversationailed "Track det""       :
 