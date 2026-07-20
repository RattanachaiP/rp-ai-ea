//+------------------------------------------------------------------+
//| RP AI V29 Executor: entry payload + Progressive TP/BE manager   |
//+------------------------------------------------------------------+
#property strict
#property version   "29.3"
#property description "V29.3 executor for AI-owned adaptive TP/BE contracts with V29 fallback."

#include <Trade/Trade.mqh>

#define V29_DECISION_PATH "RP_AI_EA\\shared\\XAUUSD\\decision.json"
#define TP1R 1.0
#define TP2R 2.0
#define TP3R 3.0

input string InpDecisionPath       = V29_DECISION_PATH;
input long   InpMagic              = 2900001;
input double InpDefaultLot         = 0.01;
input double InpExposureCapLots    = 1.00;
input double InpInitialRPoints     = 100.0; // V28 fallback when no V29 contract is supplied
input bool   InpEnableEntries      = true;
// Trader objectives only.  No TP/BE/lock ladder is configured in MT5.
input bool   InpEnableAIProgressiveTP = true;
input bool   InpEnableAIProgressiveBE = true;
input double InpBaseTakeProfitPoints  = 500.0;
input double InpBaseBreakEvenPoints   = 300.0;
input bool   InpRunRegressionTests = false;

CTrade g_trade;

struct TicketState
{
   bool   tp1_done;
   bool   tp2_done;
   bool   tp3_done;
   double current_lock;
   double partial_volume_closed;
   double initial_volume;
   double initial_r_points;
};

struct DecisionPayload
{
   string decision, direction, entry_confidence, waiting_reason;
   double lot, initial_r_points;
   double entry_score;
   long   sequence_id;
   bool   entry_allowed, has_entry_allowed;
   bool   has_entry_score, has_entry_confidence, has_waiting_reason;
   bool   has_entry_components, has_progressive_tp_contract, has_adaptive_tp_be_contract;
};

string StateKey(const ulong ticket, const string field) { return "RP_V29_TPBE_" + (string)ticket + "_" + field; }
bool StateHas(const ulong ticket, const string field) { return GlobalVariableCheck(StateKey(ticket, field)); }
double StateGet(const ulong ticket, const string field, const double fallback=0.0)
{
   return StateHas(ticket, field) ? GlobalVariableGet(StateKey(ticket, field)) : fallback;
}
void StateSet(const ulong ticket, const string field, const double value) { GlobalVariableSet(StateKey(ticket, field), value); }

// State is terminal-global-variable backed: it survives EA and terminal restarts.
TicketState LoadState(const ulong ticket, const double volume, const double initial_r)
{
   TicketState state;
   state.tp1_done = StateGet(ticket, "tp1_done") > 0.5;
   state.tp2_done = StateGet(ticket, "tp2_done") > 0.5;
   state.tp3_done = StateGet(ticket, "tp3_done") > 0.5;
   state.current_lock = StateGet(ticket, "current_lock");
   state.partial_volume_closed = StateGet(ticket, "partial_volume_closed");
   state.initial_volume = StateGet(ticket, "initial_volume", volume);
   state.initial_r_points = StateGet(ticket, "initial_r_points", initial_r);
   if(state.initial_volume <= 0.0) state.initial_volume = volume;
   if(state.initial_r_points <= 0.0) state.initial_r_points = initial_r;
   return state;
}

void SaveState(const ulong ticket, const TicketState &state)
{
   StateSet(ticket, "tp1_done", state.tp1_done ? 1.0 : 0.0);
   StateSet(ticket, "tp2_done", state.tp2_done ? 1.0 : 0.0);
   StateSet(ticket, "tp3_done", state.tp3_done ? 1.0 : 0.0);
   StateSet(ticket, "current_lock", state.current_lock);
   StateSet(ticket, "partial_volume_closed", state.partial_volume_closed);
   StateSet(ticket, "initial_volume", state.initial_volume);
   StateSet(ticket, "initial_r_points", state.initial_r_points);
}

int NextStage(const TicketState &state)
{
   if(!state.tp1_done) return 1;
   if(!state.tp2_done) return 2;
   if(!state.tp3_done) return 3;
   return 0;
}

double StageTriggerR(const int stage) { return stage == 1 ? TP1R : (stage == 2 ? TP2R : TP3R); }
double StageLockR(const int stage) { return stage == 1 ? 0.0 : (stage == 2 ? 0.5 : 1.0); }

bool IsJsonWhitespace(const ushort c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

// Root-field scanner deliberately ignores similarly named nested V29 components.
bool FindTopLevelField(const string json, const string key, int &value_start)
{
   int depth=0, length=StringLen(json); bool in_string=false, escaped=false;
   for(int i=0; i<length; i++)
   {
      ushort c=StringGetCharacter(json,i);
      if(in_string)
      {
         if(escaped) { escaped=false; continue; }
         if(c=='\\') { escaped=true; continue; }
         if(c=='"') in_string=false;
         continue;
      }
      if(c=='"')
      {
         int key_len=StringLen(key);
         if(depth==1 && StringSubstr(json,i+1,key_len)==key && i+key_len+1<length && StringGetCharacter(json,i+key_len+1)=='"')
         {
            int colon=i+key_len+2; while(colon<length && IsJsonWhitespace(StringGetCharacter(json,colon))) colon++;
            if(colon<length && StringGetCharacter(json,colon)==':')
            { value_start=colon+1; while(value_start<length && IsJsonWhitespace(StringGetCharacter(json,value_start))) value_start++; return value_start<length; }
         }
         in_string=true;
      }
      else if(c=='{' || c=='[') depth++;
      else if(c=='}' || c==']') depth--;
   }
   return false;
}

bool ReadFieldString(const string json, const string key, string &value)
{
   int start; if(!FindTopLevelField(json,key,start) || StringGetCharacter(json,start)!='"') return false;
   start++; bool escaped=false;
   for(int i=start; i<StringLen(json); i++)
   {
      ushort c=StringGetCharacter(json,i);
      if(!escaped && c=='"') { value=StringSubstr(json,start,i-start); return true; }
      if(!escaped && c=='\\') escaped=true; else escaped=false;
   }
   return false;
}
bool ReadFieldNumber(const string json, const string key, double &value)
{
   int start; if(!FindTopLevelField(json,key,start)) return false;
   int end=start; while(end<StringLen(json)) { ushort c=StringGetCharacter(json,end); if((c>='0'&&c<='9')||c=='-'||c=='+'||c=='.'||c=='e'||c=='E') end++; else break; }
   if(end==start) return false; value=StringToDouble(StringSubstr(json,start,end-start)); return true;
}
bool ReadFieldBool(const string json, const string key, bool &value)
{
   int start; if(!FindTopLevelField(json,key,start)) return false;
   string literal=StringSubstr(json,start,5); StringToLower(literal);
   if(StringSubstr(literal,0,4)=="true") { value=true; return true; }
   if(literal=="false") { value=false; return true; }
   return false;
}

bool ReadDecisionPayload(string &json)
{
   int h=FileOpen(InpDecisionPath,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(h==INVALID_HANDLE) return false;
   json=""; while(!FileIsEnding(h)) json+=FileReadString(h); FileClose(h);
   return StringLen(json)>0;
}

// V28 payloads do not consistently carry sequence_id. Keep their old schema
// usable while still preventing the same file from being submitted every tick.
double PayloadFingerprint(const string json)
{
   double hash=0.0;
   for(int i=0;i<StringLen(json);i++) hash=MathMod(hash*131.0+(double)StringGetCharacter(json,i),2147483647.0);
   return hash;
}

bool ParsePayload(const string json, DecisionPayload &payload)
{
   ZeroMemory(payload); payload.lot=InpDefaultLot; payload.initial_r_points=InpInitialRPoints;
   if(!ReadFieldString(json,"decision",payload.decision)) return false;
   if(!ReadFieldString(json,"direction",payload.direction))
      if(!ReadFieldString(json,"action",payload.direction)) ReadFieldString(json,"bias",payload.direction);
   StringToUpper(payload.decision); StringToUpper(payload.direction);
   ReadFieldNumber(json,"lot",payload.lot); ReadFieldNumber(json,"initial_r_points",payload.initial_r_points);
   double sequence=0.0; if(ReadFieldNumber(json,"sequence_id",sequence)) payload.sequence_id=(long)sequence;
   payload.has_entry_allowed=ReadFieldBool(json,"entry_allowed",payload.entry_allowed);
   payload.has_entry_score=ReadFieldNumber(json,"entry_score",payload.entry_score);
   payload.has_entry_confidence=ReadFieldString(json,"entry_confidence",payload.entry_confidence);
   payload.has_waiting_reason=ReadFieldString(json,"waiting_reason",payload.waiting_reason);
   int unused=0; payload.has_entry_components=FindTopLevelField(json,"entry_components",unused);
   payload.has_progressive_tp_contract=FindTopLevelField(json,"progressive_tp_contract",unused) || FindTopLevelField(json,"progressive_tp_be",unused);
   payload.has_adaptive_tp_be_contract=FindTopLevelField(json,"adaptive_tp_be_contract",unused);
   // adaptive_tp_be_contract is the V29.3 executor authority.  Its level
   // values are validated and persisted per ticket by the production contract
   // reader; absence deliberately selects LEGACY_V29_FALLBACK below.
   // V28 has none of the additive V29 fields; omission is explicitly compatible.
   return payload.lot>0.0 && payload.initial_r_points>0.0;
}

double NormalizeVolume(const string symbol, const double requested, const double available)
{
   double min=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN), step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0 || available<min) return 0.0;
   double volume=MathFloor(requested/step+0.0000001)*step;
   if(volume<min && requested<available) return 0.0; // do not turn TP1/TP2 into an accidental full close
   if(volume<min) volume=min; if(volume>available) volume=available;
   return NormalizeDouble(volume,2);
}

bool ImproveStop(const ulong ticket, const long type, const double open_price, const double desired_sl, TicketState &state)
{
   if(!PositionSelectByTicket(ticket)) return true; // TP3 fully closed: nothing to protect.
   double current_sl=PositionGetDouble(POSITION_SL);
   bool improves=type==POSITION_TYPE_BUY ? (current_sl==0.0 || desired_sl>current_sl) : (current_sl==0.0 || desired_sl<current_sl);
   if(!improves) return true;
   if(!g_trade.PositionModify(ticket,NormalizeDouble(desired_sl,_Digits),PositionGetDouble(POSITION_TP)))
   { PrintFormat("V29_STOP_MODIFY_FAIL | ticket=%I64u | %s",ticket,g_trade.ResultRetcodeDescription()); return false; }
   state.current_lock=MathMax(state.current_lock,MathAbs(desired_sl-open_price)/_Point/state.initial_r_points);
   return true;
}

// A close is never repeated after broker acknowledgement. If its associated
// protection was rejected, retry only the protection before advancing.
bool EnsureCompletedProtection(const ulong ticket, const long type, const double open, TicketState &state)
{
   int completed=state.tp2_done ? 2 : (state.tp1_done ? 1 : 0);
   if(completed==0) return true;
   double lock=StageLockR(completed);
   double desired=type==POSITION_TYPE_BUY ? open+lock*state.initial_r_points*_Point : open-lock*state.initial_r_points*_Point;
   return ImproveStop(ticket,type,open,desired,state);
}

void ManagePosition(const ulong ticket)
{
   if(!PositionSelectByTicket(ticket) || PositionGetInteger(POSITION_MAGIC)!=InpMagic || PositionGetString(POSITION_SYMBOL)!=_Symbol) return;
   double available=PositionGetDouble(POSITION_VOLUME); TicketState state=LoadState(ticket,available,InpInitialRPoints);
   if(state.initial_r_points<=0.0) return;
   long type=PositionGetInteger(POSITION_TYPE); double open=PositionGetDouble(POSITION_PRICE_OPEN); MqlTick tick; if(!SymbolInfoTick(_Symbol,tick)) return;
   if(!EnsureCompletedProtection(ticket,type,open,state)) { SaveState(ticket,state); return; }
   double exit_price=type==POSITION_TYPE_BUY ? tick.bid : tick.ask;
   double current_r=(type==POSITION_TYPE_BUY ? exit_price-open : open-exit_price)/_Point/state.initial_r_points;
   int stage=NextStage(state); if(stage==0 || current_r<StageTriggerR(stage)) return;

   // Stage percentages are of ORIGINAL volume: TP1=50%, TP2=25%, TP3=all remaining.
   double requested=stage==1 ? state.initial_volume*0.50 : (stage==2 ? state.initial_volume*0.25 : available);
   double close_volume=NormalizeVolume(_Symbol,requested,available);
   if(close_volume<=0.0) { PrintFormat("V29_PARTIAL_VOLUME_UNAVAILABLE | ticket=%I64u | stage=TP%d",ticket,stage); return; }
   if(!g_trade.PositionClosePartial(ticket,close_volume)) { PrintFormat("V29_PARTIAL_CLOSE_FAIL | ticket=%I64u | stage=TP%d | %s",ticket,stage,g_trade.ResultRetcodeDescription()); return; }

   // Persist completion immediately after broker success, before any next tick/restart can re-enter it.
   if(stage==1) state.tp1_done=true; else if(stage==2) state.tp2_done=true; else state.tp3_done=true;
   state.partial_volume_closed+=close_volume;
   SaveState(ticket,state);
   if(stage<3)
   {
      double lock=StageLockR(stage), desired=type==POSITION_TYPE_BUY ? open+lock*state.initial_r_points*_Point : open-lock*state.initial_r_points*_Point;
      ImproveStop(ticket,type,open,desired,state); // never moves a stop backwards
   }
   SaveState(ticket,state);
   PrintFormat("V29_TPBE_LEVEL_COMPLETED | ticket=%I64u | level=TP%d | r=%.2f | close=%s | lock=%.2fR",ticket,stage,current_r,DoubleToString(close_volume,2),state.current_lock);
}

double CurrentExposureLots(const string symbol)
{
   double total=0.0; for(int i=PositionsTotal()-1;i>=0;i--) { ulong t=PositionGetTicket(i); if(t>0 && PositionGetString(POSITION_SYMBOL)==symbol) total+=PositionGetDouble(POSITION_VOLUME); } return total;
}

void ExecutePayload()
{
   if(!InpEnableEntries) return;
   string json; if(!ReadDecisionPayload(json)) return;
   DecisionPayload payload; if(!ParsePayload(json,payload)) { Print("V29_PAYLOAD_INVALID"); return; }
   string management_mode=payload.has_adaptive_tp_be_contract ? "AI_ADAPTIVE_CONTRACT" : "LEGACY_V29_FALLBACK";
   PrintFormat("V29_PAYLOAD | decision=%s | direction=%s | entry_score=%s | confidence=%s | waiting_reason=%s | components=%s | progressive_contract=%s | adaptive_contract=%s | mode=%s",payload.decision,payload.direction,payload.has_entry_score ? DoubleToString(payload.entry_score,0) : "V28_DEFAULT",payload.has_entry_confidence ? payload.entry_confidence : "V28_DEFAULT",payload.has_waiting_reason ? payload.waiting_reason : "V28_DEFAULT",payload.has_entry_components ? "present" : "V28_DEFAULT",payload.has_progressive_tp_contract ? "present" : "V28_DEFAULT",payload.has_adaptive_tp_be_contract ? "present" : "absent",management_mode);
   // V29 producer may omit entry_allowed on a TRADE; V28 requires it when provided.
   if(payload.decision!="TRADE" || (payload.has_entry_allowed && !payload.entry_allowed) || (payload.direction!="BUY" && payload.direction!="SELL")) return;
   double fingerprint=PayloadFingerprint(json);
   if((payload.sequence_id>0 && StateGet(0,"last_sequence")==payload.sequence_id) || StateGet(0,"last_fingerprint")==fingerprint) return;
   if(payload.lot+CurrentExposureLots(_Symbol)>InpExposureCapLots || !TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) { Print("V29_BROKER_SAFETY_BLOCK"); return; }
   StateSet(0,"pending_initial_r",payload.initial_r_points);
   g_trade.SetExpertMagicNumber(InpMagic); bool sent=payload.direction=="BUY" ? g_trade.Buy(payload.lot,_Symbol) : g_trade.Sell(payload.lot,_Symbol);
   if(!sent) { PrintFormat("V29_ORDER_SEND_FAIL | %s",g_trade.ResultRetcodeDescription()); return; }
   // On the following tick LoadState persists this payload's fallback-safe R per ticket.
   for(int i=PositionsTotal()-1;i>=0;i--) { ulong ticket=PositionGetTicket(i); if(ticket>0 && PositionGetInteger(POSITION_MAGIC)==InpMagic && !StateHas(ticket,"initial_r_points")) { TicketState state=LoadState(ticket,PositionGetDouble(POSITION_VOLUME),payload.initial_r_points); SaveState(ticket,state); } }
   if(payload.sequence_id>0) StateSet(0,"last_sequence",payload.sequence_id);
   StateSet(0,"last_fingerprint",fingerprint);
   PrintFormat("V29_ORDER_SEND_OK | order=%I64u | direction=%s",g_trade.ResultOrder(),payload.direction);
}

// Covers asynchronous broker fills as well as an EA restart between OrderSend
// and the next tick, so each opened ticket receives its immutable entry R.
void OnTradeTransaction(const MqlTradeTransaction &transaction, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(transaction.type!=TRADE_TRANSACTION_DEAL_ADD || transaction.position==0) return;
   if(!HistoryDealSelect(transaction.deal) || HistoryDealGetInteger(transaction.deal,DEAL_MAGIC)!=InpMagic) return;
   if(!PositionSelectByTicket(transaction.position) || StateHas(transaction.position,"initial_r_points")) return;
   TicketState state=LoadState(transaction.position,PositionGetDouble(POSITION_VOLUME),StateGet(0,"pending_initial_r",InpInitialRPoints));
   SaveState(transaction.position,state);
}

bool AssertRegression(const bool condition, const string name) { Print((condition ? "V29_TEST_PASS | " : "V29_TEST_FAIL | ")+name); return condition; }
bool RunRegressionTests()
{
   TicketState state; ZeroMemory(state); state.initial_volume=1.0; state.initial_r_points=100.0;
   bool ok=true;
   ok &= AssertRegression(NextStage(state)==1 && StageTriggerR(1)==1.0 && StageLockR(1)==0.0,"TP1");
   state.tp1_done=true; ok &= AssertRegression(NextStage(state)==2 && StageTriggerR(2)==2.0 && StageLockR(2)==0.5,"TP2");
   state.tp2_done=true; ok &= AssertRegression(NextStage(state)==3 && StageTriggerR(3)==3.0 && StageLockR(3)==1.0,"TP3");
   TicketState gap; ZeroMemory(gap); gap.initial_volume=1.0; ok &= AssertRegression(NextStage(gap)==1,"GAP_PROCESSES_FIRST_UNFINISHED_STAGE_ONLY"); gap.tp1_done=true; ok &= AssertRegression(NextStage(gap)==2,"GAP_RESUMES_TP2");
   ulong restart_ticket=987654321; SaveState(restart_ticket,state); TicketState recovered=LoadState(restart_ticket,1.0,100.0); ok &= AssertRegression(recovered.tp1_done && recovered.tp2_done && NextStage(recovered)==3,"RESTART_RECOVERY");
   TicketState second; ZeroMemory(second); ok &= AssertRegression(NextStage(second)==1 && NextStage(recovered)==3,"MULTIPLE_POSITIONS");
   recovered.tp3_done=true; ok &= AssertRegression(NextStage(recovered)==0,"DUPLICATE_PROTECTION");
   GlobalVariableDel(StateKey(restart_ticket,"tp1_done")); GlobalVariableDel(StateKey(restart_ticket,"tp2_done")); GlobalVariableDel(StateKey(restart_ticket,"tp3_done")); GlobalVariableDel(StateKey(restart_ticket,"current_lock")); GlobalVariableDel(StateKey(restart_ticket,"partial_volume_closed")); GlobalVariableDel(StateKey(restart_ticket,"initial_volume")); GlobalVariableDel(StateKey(restart_ticket,"initial_r_points"));
   return ok;
}

int OnInit() { if(InpRunRegressionTests && !RunRegressionTests()) return INIT_FAILED; return INIT_SUCCEEDED; }
void OnTick()
{
   ExecutePayload();
   for(int i=PositionsTotal()-1;i>=0;i--) { ulong ticket=PositionGetTicket(i); if(ticket>0) ManagePosition(ticket); }
}
