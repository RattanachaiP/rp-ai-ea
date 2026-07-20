//+------------------------------------------------------------------+
//| V29 post-entry manager: Progressive TP/BE only                  |
//+------------------------------------------------------------------+
#property strict
#property version   "29.0"
#property description "V29: 1R/2R/3R partial TP and one-way break-even protection."

#include <Trade/Trade.mqh>

input long   InpMagic             = 2900001;
input double InpInitialRPoints    = 100.0;
input double InpTP1R              = 1.0;
input double InpTP2R              = 2.0;
input double InpTP3R              = 3.0;
input double InpTP1CloseFraction  = 0.50;
input double InpTP2CloseFraction  = 0.50; // half of remaining = 25% original
input double InpTP3CloseFraction  = 1.00; // all remaining = 25% original
input double InpTP2LockR          = 0.50;
input double InpTP3LockR          = 1.00;

CTrade g_trade;

string LevelKey(const ulong ticket) { return "RP_V29_TPBE_" + (string)ticket; }
int CompletedLevel(const ulong ticket) { return GlobalVariableCheck(LevelKey(ticket)) ? (int)GlobalVariableGet(LevelKey(ticket)) : 0; }
void MarkCompleted(const ulong ticket, const int level) { GlobalVariableSet(LevelKey(ticket), level); }

double NormalizeCloseVolume(const string symbol, double requested, const double available)
{
   double minimum = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || available < minimum) return 0.0;
   double volume = MathFloor(requested / step + 0.0000001) * step;
   // Never turn TP1/TP2 into a full close merely because broker minimum lot
   // prevents the requested partial volume.  The final TP3 is the only level
   // allowed to close all remaining volume.
   if(volume < minimum && requested < available) return 0.0;
   if(volume < minimum) volume = minimum;
   if(volume > available) volume = available;
   return NormalizeDouble(volume, 2);
}

bool ImproveStop(const ulong ticket, const long type, const double open_price, const double desired_sl)
{
   if(!PositionSelectByTicket(ticket)) return false;
   double current_sl = PositionGetDouble(POSITION_SL);
   // A BUY stop must rise; a SELL stop must fall.  This is the one-way BE rule.
   bool improves = type == POSITION_TYPE_BUY ? (current_sl == 0.0 || desired_sl > current_sl)
                                             : (current_sl == 0.0 || desired_sl < current_sl);
   if(!improves) return true;
   double tp = PositionGetDouble(POSITION_TP);
   if(!g_trade.PositionModify(ticket, NormalizeDouble(desired_sl, _Digits), tp))
   {
      PrintFormat("V29_TPBE_STOP_MODIFY_FAIL | ticket=%I64u | %s", ticket, g_trade.ResultRetcodeDescription());
      return false;
   }
   PrintFormat("V29_TPBE_STOP_PROTECTED | ticket=%I64u | sl=%s", ticket, DoubleToString(desired_sl, _Digits));
   return true;
}

void ManagePosition(const ulong ticket)
{
   if(!PositionSelectByTicket(ticket)) return;
   if(PositionGetInteger(POSITION_MAGIC) != InpMagic || PositionGetString(POSITION_SYMBOL) != _Symbol) return;
   if(InpInitialRPoints <= 0.0) { Print("V29_TPBE_INVALID_INITIAL_R"); return; }
   long type = PositionGetInteger(POSITION_TYPE);
   double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;
   double exit_price = type == POSITION_TYPE_BUY ? tick.bid : tick.ask;
   double profit_points = (type == POSITION_TYPE_BUY ? exit_price - open_price : open_price - exit_price) / _Point;
   double current_r = profit_points / InpInitialRPoints;
   int done = CompletedLevel(ticket);
   int next_level = done + 1;
   double trigger = next_level == 1 ? InpTP1R : (next_level == 2 ? InpTP2R : InpTP3R);
   if(next_level > 3 || current_r < trigger) return;

   double lock_r = next_level == 1 ? 0.0 : (next_level == 2 ? InpTP2LockR : InpTP3LockR);
   double desired_sl = type == POSITION_TYPE_BUY ? open_price + lock_r * InpInitialRPoints * _Point
                                                  : open_price - lock_r * InpInitialRPoints * _Point;
   double fraction = next_level == 1 ? InpTP1CloseFraction : (next_level == 2 ? InpTP2CloseFraction : InpTP3CloseFraction);
   double volume = NormalizeCloseVolume(_Symbol, PositionGetDouble(POSITION_VOLUME) * fraction, PositionGetDouble(POSITION_VOLUME));
   if(volume <= 0.0)
   {
      PrintFormat("V29_TPBE_PARTIAL_VOLUME_UNAVAILABLE | ticket=%I64u | level=TP%d", ticket, next_level);
      return;
   }
   if(!g_trade.PositionClosePartial(ticket, volume))
   {
      PrintFormat("V29_TPBE_PARTIAL_CLOSE_FAIL | ticket=%I64u | level=TP%d | %s", ticket, next_level, g_trade.ResultRetcodeDescription());
      return;
   }
   // A completed target is the only event allowed to advance protection.
   // TP3 may have closed the position, in which case no stop remains to move.
   if(next_level < 3) ImproveStop(ticket, type, open_price, desired_sl);
   MarkCompleted(ticket, next_level);
   PrintFormat("V29_TPBE_LEVEL_COMPLETED | ticket=%I64u | level=TP%d | r=%.2f | volume=%s", ticket, next_level, current_r, DoubleToString(volume, 2));
}

void OnTick()
{
   for(int index = PositionsTotal() - 1; index >= 0; --index)
   {
      ulong ticket = PositionGetTicket(index);
      if(ticket > 0) ManagePosition(ticket);
   }
}
