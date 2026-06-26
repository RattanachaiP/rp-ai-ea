//+------------------------------------------------------------------+
//| RP AI Executor V28 Clean Core                                    |
//| Strategy-free executor contract example for V28.                 |
//+------------------------------------------------------------------+
#property strict
#property version "28.00"
#property description "V28 clean executor: validates payload contract, broker safety, then OrderSend. No legacy strategy gates."

#include <Trade/Trade.mqh>

input string InpDecisionFile = "decision_v28.json";
input int    InpMaxDecisionAgeSeconds = 15;
input int    InpMaxSpreadPoints = 250;
input long   InpMagic = 2800001;

CTrade g_trade;

string ReadCommonFile(const string file_name)
{
   int handle = FileOpen(file_name, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return "";
   string text = "";
   while(!FileIsEnding(handle)) text += FileReadString(handle) + "\n";
   FileClose(handle);
   return text;
}

string JsonString(const string json, const string key, const string fallback="")
{
   string pattern = "\"" + key + "\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return fallback;
   int colon = StringFind(json, ":", pos);
   int first = StringFind(json, "\"", colon + 1);
   int second = StringFind(json, "\"", first + 1);
   if(colon < 0 || first < 0 || second < 0) return fallback;
   return StringSubstr(json, first + 1, second - first - 1);
}

double JsonNumber(const string json, const string key, const double fallback=0.0)
{
   string pattern = "\"" + key + "\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return fallback;
   int colon = StringFind(json, ":", pos);
   if(colon < 0) return fallback;
   int end = colon + 1;
   while(end < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, end);
      if((ch >= '0' && ch <= '9') || ch == '-' || ch == '.' || ch == 'e' || ch == 'E') end++;
      else if(ch == ' ' || ch == '\t') end++;
      else break;
   }
   return StringToDouble(StringSubstr(json, colon + 1, end - colon - 1));
}

bool JsonBool(const string json, const string key, const bool fallback=false)
{
   string pattern = "\"" + key + "\"";
   int pos = StringFind(json, pattern);
   if(pos < 0) return fallback;
   int colon = StringFind(json, ":", pos);
   if(colon < 0) return fallback;
   string tail = StringSubstr(json, colon + 1, 8);
   StringToLower(tail);
   if(StringFind(tail, "true") >= 0) return true;
   if(StringFind(tail, "false") >= 0) return false;
   return fallback;
}

bool BrokerSafetyPass(const string symbol, string &reason)
{
   if(!SymbolInfoInteger(symbol, SYMBOL_SELECT) && !SymbolSelect(symbol, true))
   {
      reason = "BROKER_SYMBOL_UNAVAILABLE";
      return false;
   }
   long spread = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)
   {
      reason = "BROKER_ABNORMAL_SPREAD";
      return false;
   }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      reason = "BROKER_TRADING_DISABLED";
      return false;
   }
   reason = "BROKER_SAFETY_PASS";
   return true;
}

bool ContractPass(const string json, string &reason)
{
   if(JsonString(json, "schema_version") != "V28_EXECUTABLE_PAYLOAD_1") { reason = "INVALID_SCHEMA"; return false; }
   if(JsonString(json, "decision") != "TRADE") { reason = "NO_TRADE_PAYLOAD"; return false; }
   string direction = JsonString(json, "direction");
   if(direction != "BUY" && direction != "SELL") { reason = "INVALID_CONTRACT_DIRECTION"; return false; }
   if(!JsonBool(json, "payload_valid")) { reason = "INVALID_CONTRACT_PAYLOAD_VALID_FALSE"; return false; }
   if(JsonNumber(json, "entry_price") <= 0.0 || JsonNumber(json, "lot") <= 0.0) { reason = "INVALID_CONTRACT_PRICE_OR_LOT"; return false; }
   bool sl_required = JsonBool(json, "broker_sl_required");
   bool tp_required = JsonBool(json, "broker_tp_required");
   if(sl_required && JsonNumber(json, "stop_loss") <= 0.0) { reason = "INVALID_CONTRACT_MISSING_SL"; return false; }
   if(tp_required && JsonNumber(json, "take_profit") <= 0.0) { reason = "INVALID_CONTRACT_MISSING_TP"; return false; }
   reason = "EXECUTOR_CONTRACT_PASS";
   return true;
}

void OnTick()
{
   string json = ReadCommonFile(InpDecisionFile);
   if(json == "") return;
   string reason;
   if(!ContractPass(json, reason)) { Print(reason); return; }
   string trade_uuid = JsonString(json, "trade_uuid", "");
   Print("EXECUTOR_CONTRACT_SNAPSHOT | trade_uuid=", trade_uuid, " | decision=", JsonString(json, "decision"), " | sl=", JsonNumber(json, "stop_loss"), " | tp=", JsonNumber(json, "take_profit"), " | order_send_attempt=false");
   Print("EXECUTOR_CONTRACT_PASS profile=", JsonString(json, "dashboard_profile"), " mode=", JsonString(json, "management_mode"));

   string symbol = JsonString(json, "symbol", _Symbol);
   if(!BrokerSafetyPass(symbol, reason)) { Print(reason); return; }

   string direction = JsonString(json, "direction");
   double lot = JsonNumber(json, "lot");
   double sl = JsonNumber(json, "stop_loss");
   double tp = JsonNumber(json, "take_profit");
   g_trade.SetExpertMagicNumber(InpMagic);
   string comment = trade_uuid == "" ? "RP_V28" : StringSubstr(trade_uuid, 0, 24);
   Print("EXECUTOR_CONTRACT_SNAPSHOT | trade_uuid=", trade_uuid, " | decision=", JsonString(json, "decision"), " | sl=", sl, " | tp=", tp, " | order_send_attempt=true");
   Print("ORDER_SEND_ATTEMPT direction=", direction, " lot=", lot, " sl=", sl, " tp=", tp, " comment=", comment);
   bool ok = direction == "BUY" ? g_trade.Buy(lot, symbol, 0.0, sl, tp, comment) : g_trade.Sell(lot, symbol, 0.0, sl, tp, comment);
   if(ok) Print("ORDER_SEND_OK ticket=", g_trade.ResultOrder());
   else Print("ORDER_SEND_FAIL retcode=", g_trade.ResultRetcode(), " description=", g_trade.ResultRetcodeDescription());
}
