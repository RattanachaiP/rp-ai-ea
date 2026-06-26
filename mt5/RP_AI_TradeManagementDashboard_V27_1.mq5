//+------------------------------------------------------------------+
//| RP AI Trade Management Dashboard V27.1                           |
//| On-chart MT5 dashboard for post-entry trade management only.      |
//+------------------------------------------------------------------+
#property strict
#property version   "27.30"
#property description "V27.3 Exit Optimization Dashboard - post-entry management only"

#include <Trade/Trade.mqh>

input string InpDashboardJsonFile = "trade_management_dashboard.json";
input string InpProfilesFolder    = "dashboard_profiles";
input string InpDefaultProfile    = "Balanced";
input int    InpChartCorner       = CORNER_LEFT_UPPER;
input int    InpX                 = 12;
input int    InpY                 = 24;
input int    InpTimerSeconds      = 2;
input bool   InpManageOpenTrades  = true;
input string InpTradeStatisticsCsv = "RP_AI_EA\\analysis\\trade_statistics.csv";
input double InpBeFalseTriggerThresholdUsd = 0.20;

#define RP_DASH_SCHEMA "V27_TRADE_MANAGEMENT_DASHBOARD_SCHEMA_1"
#define RP_PREFIX      "RP_V273_TMD_"
#define TRADE_STATS_RELATIVE_PATH "RP_AI_EA\\analysis\\trade_statistics.csv"
#define TRADE_STATS_SCHEMA_VERSION "V27_3_5_EXIT_EVIDENCE_AUDIT"
#define DECISION_JSON_FILE "decision.json"
#define MARKET_STATE_JSON_FILE "market_state.json"

struct DashboardConfig
{
   string active_profile;
   bool enabled;
   double initial_sl_usd_001_lot;
   double hard_loss_cap_usd_001_lot;
   double max_floating_loss_usd_001_lot;
   bool emergency_close;
   bool breakeven_enable;
   double breakeven_trigger_usd_001_lot;
   double breakeven_offset_usd_001_lot;
   int minimum_hold_seconds_before_be;
   double minimum_noise_safe_be_usd;
   bool atr_be_enabled;
   double atr_be_multiplier;
   double max_spread_points;
   bool runner_be;
   bool trailing_enable;
   double trailing_start_usd_001_lot;
   double trailing_distance_usd_001_lot;
   double trailing_step_usd_001_lot;
   bool atr_trail_enable;
   bool profit_lock_enable;
   double lock1_trigger;
   double lock1_lock;
   double lock2_trigger;
   double lock2_lock;
   double lock3_trigger;
   double lock3_lock;
   double minimum_locked_profit_usd_001_lot;
   bool fixed_take_profit_enable;
   double fixed_take_profit_close_usd_001_lot;
   bool runner_enable;
   int runner_timeout_seconds;
   string runner_trail;
   double runner_sl_usd_001_lot;
   bool momentum_confirmation;
   bool time_exit_enable;
   int maximum_seconds;
   int maximum_bars;
   bool partial_enable;
   int partial_level_1_percent;
   int partial_level_2_percent;
   int remaining_runner_percent;
   string load_status;
   bool fallback_defaults_used;
};

DashboardConfig g_cfg;
CTrade g_trade;
datetime g_last_load = 0;
string g_status = "starting";

ulong g_track_tickets[];
double g_track_mfe[];
double g_track_mae[];
bool g_track_be_enabled[];
double g_track_be_trigger_price[];
double g_track_be_trigger_profit_usd[];
datetime g_track_be_trigger_time[];
int g_track_be_trigger_after_seconds[];
double g_track_be_sl_price[];
double g_track_be_offset_usd[];
bool g_track_be_stop_out[];
double g_track_profit_before_be_stop_out[];
double g_track_max_profit_after_be_trigger[];
double g_track_min_profit_after_be_trigger[];
double g_track_lost_opportunity_after_be[];
double g_track_order_sl_at_open[];
double g_track_order_tp_at_open[];
double g_track_position_sl_last[];
double g_track_position_tp_last[];
datetime g_track_mfe_time[];
datetime g_track_mae_time[];
double g_track_price_at_mfe[];
double g_track_price_at_mae[];
string g_track_dashboard_close_intent[];
string g_track_decision_uuid[];
double g_track_sequence_id[];
double g_track_heartbeat_unix[];
double g_track_market_state_age_sec[];
double g_track_decision_age_sec[];
string g_track_action[];
string g_track_bias[];
string g_track_mode[];
string g_track_bb_state[];
double g_track_rsi[];
double g_track_macd_hist[];
double g_track_adx[];
double g_track_atr[];
double g_track_spread_points_entry[];
double g_track_buy_score[];
double g_track_sell_score[];
double g_track_score_gap[];
string g_track_dominant_direction[];
string g_track_execution_state[];
string g_track_management_mode[];
string g_track_dashboard_profile_at_entry[];

double EffectiveBeTriggerUsd001Lot();
string ReadCommonFile(const string file_name);
string JsonString(const string json, const string key, const string fallback);
double JsonNumber(const string json, const string key, const double fallback);

int TrackIndex(const ulong ticket)
{
   for(int i = 0; i < ArraySize(g_track_tickets); ++i)
      if(g_track_tickets[i] == ticket) return i;
   return -1;
}

int EnsureTrack(const ulong ticket)
{
   int idx = TrackIndex(ticket);
   if(idx >= 0) return idx;
   int n = ArraySize(g_track_tickets);
   ArrayResize(g_track_tickets, n + 1);
   ArrayResize(g_track_mfe, n + 1);
   ArrayResize(g_track_mae, n + 1);
   ArrayResize(g_track_be_enabled, n + 1);
   ArrayResize(g_track_be_trigger_price, n + 1);
   ArrayResize(g_track_be_trigger_profit_usd, n + 1);
   ArrayResize(g_track_be_trigger_time, n + 1);
   ArrayResize(g_track_be_trigger_after_seconds, n + 1);
   ArrayResize(g_track_be_sl_price, n + 1);
   ArrayResize(g_track_be_offset_usd, n + 1);
   ArrayResize(g_track_be_stop_out, n + 1);
   ArrayResize(g_track_profit_before_be_stop_out, n + 1);
   ArrayResize(g_track_max_profit_after_be_trigger, n + 1);
   ArrayResize(g_track_min_profit_after_be_trigger, n + 1);
   ArrayResize(g_track_lost_opportunity_after_be, n + 1);
   ArrayResize(g_track_order_sl_at_open, n + 1);
   ArrayResize(g_track_order_tp_at_open, n + 1);
   ArrayResize(g_track_position_sl_last, n + 1);
   ArrayResize(g_track_position_tp_last, n + 1);
   ArrayResize(g_track_mfe_time, n + 1);
   ArrayResize(g_track_mae_time, n + 1);
   ArrayResize(g_track_price_at_mfe, n + 1);
   ArrayResize(g_track_price_at_mae, n + 1);
   ArrayResize(g_track_dashboard_close_intent, n + 1);
   ArrayResize(g_track_decision_uuid, n + 1);
   ArrayResize(g_track_sequence_id, n + 1);
   ArrayResize(g_track_heartbeat_unix, n + 1);
   ArrayResize(g_track_market_state_age_sec, n + 1);
   ArrayResize(g_track_decision_age_sec, n + 1);
   ArrayResize(g_track_action, n + 1);
   ArrayResize(g_track_bias, n + 1);
   ArrayResize(g_track_mode, n + 1);
   ArrayResize(g_track_bb_state, n + 1);
   ArrayResize(g_track_rsi, n + 1);
   ArrayResize(g_track_macd_hist, n + 1);
   ArrayResize(g_track_adx, n + 1);
   ArrayResize(g_track_atr, n + 1);
   ArrayResize(g_track_spread_points_entry, n + 1);
   ArrayResize(g_track_buy_score, n + 1);
   ArrayResize(g_track_sell_score, n + 1);
   ArrayResize(g_track_score_gap, n + 1);
   ArrayResize(g_track_dominant_direction, n + 1);
   ArrayResize(g_track_execution_state, n + 1);
   ArrayResize(g_track_management_mode, n + 1);
   ArrayResize(g_track_dashboard_profile_at_entry, n + 1);
   g_track_tickets[n] = ticket;
   g_track_mfe[n] = 0.0;
   g_track_mae[n] = 0.0;
   g_track_be_enabled[n] = false;
   g_track_be_trigger_price[n] = 0.0;
   g_track_be_trigger_profit_usd[n] = 0.0;
   g_track_be_trigger_time[n] = 0;
   g_track_be_trigger_after_seconds[n] = 0;
   g_track_be_sl_price[n] = 0.0;
   g_track_be_offset_usd[n] = 0.0;
   g_track_be_stop_out[n] = false;
   g_track_profit_before_be_stop_out[n] = 0.0;
   g_track_max_profit_after_be_trigger[n] = 0.0;
   g_track_min_profit_after_be_trigger[n] = 0.0;
   g_track_lost_opportunity_after_be[n] = 0.0;
   g_track_order_sl_at_open[n] = PositionSelectByTicket(ticket) ? PositionGetDouble(POSITION_SL) : 0.0;
   g_track_order_tp_at_open[n] = PositionSelectByTicket(ticket) ? PositionGetDouble(POSITION_TP) : 0.0;
   g_track_position_sl_last[n] = g_track_order_sl_at_open[n];
   g_track_position_tp_last[n] = g_track_order_tp_at_open[n];
   g_track_mfe_time[n] = 0;
   g_track_mae_time[n] = 0;
   g_track_price_at_mfe[n] = 0.0;
   g_track_price_at_mae[n] = 0.0;
   g_track_dashboard_close_intent[n] = "";
   string decision_json = ReadCommonFile(DECISION_JSON_FILE);
   string market_json = ReadCommonFile(MARKET_STATE_JSON_FILE);
   g_track_decision_uuid[n] = JsonString(decision_json, "decision_uuid", JsonString(decision_json, "uuid", ""));
   g_track_sequence_id[n] = JsonNumber(decision_json, "sequence_id", 0.0);
   g_track_heartbeat_unix[n] = JsonNumber(decision_json, "heartbeat_unix", 0.0);
   g_track_market_state_age_sec[n] = JsonNumber(decision_json, "market_state_age_sec", 0.0);
   g_track_decision_age_sec[n] = JsonNumber(decision_json, "decision_age_sec", 0.0);
   g_track_action[n] = JsonString(decision_json, "action", JsonString(decision_json, "decision", ""));
   g_track_bias[n] = JsonString(decision_json, "bias", "");
   g_track_mode[n] = JsonString(decision_json, "mode", "");
   g_track_bb_state[n] = JsonString(decision_json, "bb_state", "");
   g_track_rsi[n] = JsonNumber(decision_json, "rsi", JsonNumber(market_json, "rsi", 0.0));
   g_track_macd_hist[n] = JsonNumber(decision_json, "macd_hist", JsonNumber(market_json, "macd_hist", 0.0));
   g_track_adx[n] = JsonNumber(decision_json, "adx", JsonNumber(market_json, "adx", 0.0));
   g_track_atr[n] = JsonNumber(decision_json, "atr", JsonNumber(market_json, "atr", 0.0));
   g_track_spread_points_entry[n] = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   g_track_buy_score[n] = JsonNumber(decision_json, "buy_score", 0.0);
   g_track_sell_score[n] = JsonNumber(decision_json, "sell_score", 0.0);
   g_track_score_gap[n] = JsonNumber(decision_json, "score_gap", MathAbs(g_track_buy_score[n] - g_track_sell_score[n]));
   g_track_dominant_direction[n] = JsonString(decision_json, "dominant_direction", "");
   g_track_execution_state[n] = JsonString(decision_json, "execution_state", JsonString(decision_json, "execution_window_state", ""));
   g_track_management_mode[n] = JsonString(decision_json, "management_mode", JsonString(decision_json, "effective_management_mode", ""));
   g_track_dashboard_profile_at_entry[n] = g_cfg.active_profile;
   return n;
}

void RemoveTrack(const ulong ticket)
{
   int idx = TrackIndex(ticket);
   if(idx < 0) return;
   int last = ArraySize(g_track_tickets) - 1;
   if(idx != last)
   {
      g_track_tickets[idx] = g_track_tickets[last];
      g_track_mfe[idx] = g_track_mfe[last];
      g_track_mae[idx] = g_track_mae[last];
      g_track_be_enabled[idx] = g_track_be_enabled[last];
      g_track_be_trigger_price[idx] = g_track_be_trigger_price[last];
      g_track_be_trigger_profit_usd[idx] = g_track_be_trigger_profit_usd[last];
      g_track_be_trigger_time[idx] = g_track_be_trigger_time[last];
      g_track_be_trigger_after_seconds[idx] = g_track_be_trigger_after_seconds[last];
      g_track_be_sl_price[idx] = g_track_be_sl_price[last];
      g_track_be_offset_usd[idx] = g_track_be_offset_usd[last];
      g_track_be_stop_out[idx] = g_track_be_stop_out[last];
      g_track_profit_before_be_stop_out[idx] = g_track_profit_before_be_stop_out[last];
      g_track_max_profit_after_be_trigger[idx] = g_track_max_profit_after_be_trigger[last];
      g_track_min_profit_after_be_trigger[idx] = g_track_min_profit_after_be_trigger[last];
      g_track_lost_opportunity_after_be[idx] = g_track_lost_opportunity_after_be[last];
      g_track_order_sl_at_open[idx] = g_track_order_sl_at_open[last];
      g_track_order_tp_at_open[idx] = g_track_order_tp_at_open[last];
      g_track_position_sl_last[idx] = g_track_position_sl_last[last];
      g_track_position_tp_last[idx] = g_track_position_tp_last[last];
      g_track_mfe_time[idx] = g_track_mfe_time[last];
      g_track_mae_time[idx] = g_track_mae_time[last];
      g_track_price_at_mfe[idx] = g_track_price_at_mfe[last];
      g_track_price_at_mae[idx] = g_track_price_at_mae[last];
      g_track_dashboard_close_intent[idx] = g_track_dashboard_close_intent[last];
      g_track_decision_uuid[idx] = g_track_decision_uuid[last];
      g_track_sequence_id[idx] = g_track_sequence_id[last];
      g_track_heartbeat_unix[idx] = g_track_heartbeat_unix[last];
      g_track_market_state_age_sec[idx] = g_track_market_state_age_sec[last];
      g_track_decision_age_sec[idx] = g_track_decision_age_sec[last];
      g_track_action[idx] = g_track_action[last];
      g_track_bias[idx] = g_track_bias[last];
      g_track_mode[idx] = g_track_mode[last];
      g_track_bb_state[idx] = g_track_bb_state[last];
      g_track_rsi[idx] = g_track_rsi[last];
      g_track_macd_hist[idx] = g_track_macd_hist[last];
      g_track_adx[idx] = g_track_adx[last];
      g_track_atr[idx] = g_track_atr[last];
      g_track_spread_points_entry[idx] = g_track_spread_points_entry[last];
      g_track_buy_score[idx] = g_track_buy_score[last];
      g_track_sell_score[idx] = g_track_sell_score[last];
      g_track_score_gap[idx] = g_track_score_gap[last];
      g_track_dominant_direction[idx] = g_track_dominant_direction[last];
      g_track_execution_state[idx] = g_track_execution_state[last];
      g_track_management_mode[idx] = g_track_management_mode[last];
      g_track_dashboard_profile_at_entry[idx] = g_track_dashboard_profile_at_entry[last];
   }
   ArrayResize(g_track_tickets, last);
   ArrayResize(g_track_mfe, last);
   ArrayResize(g_track_mae, last);
   ArrayResize(g_track_be_enabled, last);
   ArrayResize(g_track_be_trigger_price, last);
   ArrayResize(g_track_be_trigger_profit_usd, last);
   ArrayResize(g_track_be_trigger_time, last);
   ArrayResize(g_track_be_trigger_after_seconds, last);
   ArrayResize(g_track_be_sl_price, last);
   ArrayResize(g_track_be_offset_usd, last);
   ArrayResize(g_track_be_stop_out, last);
   ArrayResize(g_track_profit_before_be_stop_out, last);
   ArrayResize(g_track_max_profit_after_be_trigger, last);
   ArrayResize(g_track_min_profit_after_be_trigger, last);
   ArrayResize(g_track_lost_opportunity_after_be, last);
   ArrayResize(g_track_order_sl_at_open, last);
   ArrayResize(g_track_order_tp_at_open, last);
   ArrayResize(g_track_position_sl_last, last);
   ArrayResize(g_track_position_tp_last, last);
   ArrayResize(g_track_mfe_time, last);
   ArrayResize(g_track_mae_time, last);
   ArrayResize(g_track_price_at_mfe, last);
   ArrayResize(g_track_price_at_mae, last);
   ArrayResize(g_track_dashboard_close_intent, last);
   ArrayResize(g_track_decision_uuid, last);
   ArrayResize(g_track_sequence_id, last);
   ArrayResize(g_track_heartbeat_unix, last);
   ArrayResize(g_track_market_state_age_sec, last);
   ArrayResize(g_track_decision_age_sec, last);
   ArrayResize(g_track_action, last);
   ArrayResize(g_track_bias, last);
   ArrayResize(g_track_mode, last);
   ArrayResize(g_track_bb_state, last);
   ArrayResize(g_track_rsi, last);
   ArrayResize(g_track_macd_hist, last);
   ArrayResize(g_track_adx, last);
   ArrayResize(g_track_atr, last);
   ArrayResize(g_track_spread_points_entry, last);
   ArrayResize(g_track_buy_score, last);
   ArrayResize(g_track_sell_score, last);
   ArrayResize(g_track_score_gap, last);
   ArrayResize(g_track_dominant_direction, last);
   ArrayResize(g_track_execution_state, last);
   ArrayResize(g_track_management_mode, last);
   ArrayResize(g_track_dashboard_profile_at_entry, last);
}

void ApplyBackwardCompatibleDefaults(DashboardConfig &cfg)
{
   cfg.active_profile = "Profile_A";
   cfg.enabled = true;
   cfg.initial_sl_usd_001_lot = 1.00;
   cfg.emergency_close = true;
   cfg.hard_loss_cap_usd_001_lot = 1.00;
   cfg.max_floating_loss_usd_001_lot = 0.80;
   cfg.breakeven_enable = false;
   cfg.breakeven_trigger_usd_001_lot = 1.50;
   cfg.breakeven_offset_usd_001_lot = 0.20;
   cfg.minimum_hold_seconds_before_be = 20;
   cfg.minimum_noise_safe_be_usd = 1.20;
   cfg.atr_be_enabled = true;
   cfg.atr_be_multiplier = 1.10;
   cfg.max_spread_points = 35.0;
   cfg.runner_be = false;
   cfg.trailing_enable = false;
   cfg.trailing_start_usd_001_lot = 0.80;
   cfg.trailing_distance_usd_001_lot = 0.30;
   cfg.trailing_step_usd_001_lot = 0.10;
   cfg.atr_trail_enable = false;
   cfg.profit_lock_enable = false;
   cfg.lock1_trigger = 0.50; cfg.lock1_lock = 0.00;
   cfg.lock2_trigger = 0.80; cfg.lock2_lock = 0.10;
   cfg.lock3_trigger = 1.20; cfg.lock3_lock = 0.40;
   cfg.minimum_locked_profit_usd_001_lot = 0.05;
   cfg.fixed_take_profit_enable = true;
   cfg.fixed_take_profit_close_usd_001_lot = 1.00;
   cfg.runner_enable = false;
   cfg.runner_timeout_seconds = 45;
   cfg.runner_trail = "STRUCTURE_MOMENTUM_BB_WALK";
   cfg.runner_sl_usd_001_lot = 1.00;
   cfg.momentum_confirmation = false;
   cfg.time_exit_enable = false;
   cfg.maximum_seconds = 0;
   cfg.maximum_bars = 0;
   cfg.partial_enable = false;
   cfg.partial_level_1_percent = 0;
   cfg.partial_level_2_percent = 0;
   cfg.remaining_runner_percent = 100;
   cfg.load_status = "embedded V26.6-compatible defaults";
   cfg.fallback_defaults_used = true;
}

bool IsTpOnlyProfileActive()
{
   return g_cfg.active_profile == "TP_ONLY_1USD_TEST";
}

void EnforceTpOnlyProfileRuntime()
{
   if(!IsTpOnlyProfileActive()) return;
   Print("TP_ONLY_PROFILE_DETECTED");
   Print("TP_ONLY_PRODUCTION_BLOCK");
   Print("AUTO_FALLBACK_TO_BALANCED");
   g_cfg.active_profile = "Balanced";
   g_cfg.initial_sl_usd_001_lot = 1.00;
   g_cfg.breakeven_enable = true;
   g_cfg.runner_be = true;
   g_cfg.trailing_enable = true;
   g_cfg.atr_trail_enable = false;
   g_cfg.profit_lock_enable = true;
   g_cfg.fixed_take_profit_enable = false;
   g_cfg.fixed_take_profit_close_usd_001_lot = 1.00;
   g_cfg.runner_enable = true;
   g_cfg.runner_timeout_seconds = 45;
   g_cfg.runner_trail = "STRUCTURE_MOMENTUM_BB_WALK";
   g_cfg.runner_sl_usd_001_lot = 1.00;
   g_cfg.momentum_confirmation = true;
}

string ReadCommonFile(const string file_name)
{
   int handle = FileOpen(file_name, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return "";
   string text = "";
   while(!FileIsEnding(handle))
      text += FileReadString(handle) + "\n";
   FileClose(handle);
   return text;
}

bool WriteCommonFile(const string file_name, const string text)
{
   int handle = FileOpen(file_name, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return false;
   FileWriteString(handle, text);
   FileClose(handle);
   return true;
}

string JsonString(const string json, const string key, const string fallback)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return fallback;
   int c = StringFind(json, ":", p);
   int q1 = StringFind(json, "\"", c + 1);
   int q2 = StringFind(json, "\"", q1 + 1);
   if(c < 0 || q1 < 0 || q2 < 0) return fallback;
   return StringSubstr(json, q1 + 1, q2 - q1 - 1);
}

double JsonNumber(const string json, const string key, const double fallback)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return fallback;
   int c = StringFind(json, ":", p);
   if(c < 0) return fallback;
   int e = c + 1;
   while(e < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, e);
      if((ch >= '0' && ch <= '9') || ch == '-' || ch == '+' || ch == '.') e++;
      else if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n') e++;
      else break;
   }
   return StringToDouble(StringSubstr(json, c + 1, e - c - 1));
}


string JsonSection(const string json, const string key)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return "";
   int c = StringFind(json, ":", p);
   int start = StringFind(json, "{", c);
   if(c < 0 || start < 0) return "";
   int depth = 0;
   for(int i = start; i < StringLen(json); ++i)
   {
      ushort ch = StringGetCharacter(json, i);
      if(ch == '{') depth++;
      else if(ch == '}')
      {
         depth--;
         if(depth == 0) return StringSubstr(json, start, i - start + 1);
      }
   }
   return "";
}

bool JsonBool(const string json, const string key, const bool fallback)
{
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return fallback;
   int c = StringFind(json, ":", p);
   if(c < 0) return fallback;
   string tail = StringSubstr(json, c + 1, 8);
   StringToLower(tail);
   if(StringFind(tail, "true") >= 0) return true;
   if(StringFind(tail, "false") >= 0) return false;
   return fallback;
}


double ClampDouble(const double value, const double lo, const double hi)
{
   if(value < lo) return lo;
   if(value > hi) return hi;
   return value;
}

int ClampInt(const int value, const int lo, const int hi)
{
   if(value < lo) return lo;
   if(value > hi) return hi;
   return value;
}

void ValidateConfig(DashboardConfig &cfg)
{
   cfg.initial_sl_usd_001_lot = ClampDouble(cfg.initial_sl_usd_001_lot, 0.01, 100.0);
   cfg.hard_loss_cap_usd_001_lot = ClampDouble(cfg.hard_loss_cap_usd_001_lot, 0.01, 100.0);
   cfg.max_floating_loss_usd_001_lot = ClampDouble(cfg.max_floating_loss_usd_001_lot, 0.01, 100.0);
   cfg.breakeven_trigger_usd_001_lot = ClampDouble(cfg.breakeven_trigger_usd_001_lot, 0.0, 100.0);
   cfg.breakeven_offset_usd_001_lot = ClampDouble(cfg.breakeven_offset_usd_001_lot, 0.0, 100.0);
   cfg.minimum_hold_seconds_before_be = ClampInt(cfg.minimum_hold_seconds_before_be, 0, 86400);
   cfg.minimum_noise_safe_be_usd = ClampDouble(cfg.minimum_noise_safe_be_usd, 0.0, 100.0);
   cfg.atr_be_multiplier = ClampDouble(cfg.atr_be_multiplier, 0.0, 10.0);
   cfg.max_spread_points = ClampDouble(cfg.max_spread_points, 0.0, 10000.0);
   cfg.trailing_start_usd_001_lot = ClampDouble(cfg.trailing_start_usd_001_lot, 0.0, 100.0);
   cfg.trailing_distance_usd_001_lot = ClampDouble(cfg.trailing_distance_usd_001_lot, 0.01, 100.0);
   cfg.trailing_step_usd_001_lot = ClampDouble(cfg.trailing_step_usd_001_lot, 0.01, 100.0);
   cfg.lock1_trigger = ClampDouble(cfg.lock1_trigger, 0.0, 100.0);
   cfg.lock1_lock = ClampDouble(cfg.lock1_lock, -10.0, 100.0);
   cfg.lock2_trigger = ClampDouble(cfg.lock2_trigger, 0.0, 100.0);
   cfg.lock2_lock = ClampDouble(cfg.lock2_lock, -10.0, 100.0);
   cfg.lock3_trigger = ClampDouble(cfg.lock3_trigger, 0.0, 100.0);
   cfg.lock3_lock = ClampDouble(cfg.lock3_lock, -10.0, 100.0);
   cfg.minimum_locked_profit_usd_001_lot = ClampDouble(cfg.minimum_locked_profit_usd_001_lot, 0.0, 100.0);
   cfg.fixed_take_profit_close_usd_001_lot = ClampDouble(cfg.fixed_take_profit_close_usd_001_lot, 0.01, 100.0);
   cfg.runner_timeout_seconds = ClampInt(cfg.runner_timeout_seconds, 0, 86400);
   cfg.runner_sl_usd_001_lot = ClampDouble(cfg.runner_sl_usd_001_lot, 0.0, 100.0);
   cfg.maximum_seconds = ClampInt(cfg.maximum_seconds, 0, 86400);
   cfg.maximum_bars = ClampInt(cfg.maximum_bars, 0, 10000);
   cfg.partial_level_1_percent = ClampInt(cfg.partial_level_1_percent, 0, 100);
   cfg.partial_level_2_percent = ClampInt(cfg.partial_level_2_percent, 0, 100);
   cfg.remaining_runner_percent = ClampInt(cfg.remaining_runner_percent, 0, 100);
   EnforceTpOnlyProfileRuntime();
}

void OverlayJson(DashboardConfig &cfg, const string json)
{
   cfg.active_profile = JsonString(json, "active_profile", cfg.active_profile);
   cfg.enabled = JsonBool(json, "enabled", cfg.enabled);
   string risk = JsonSection(json, "risk");
   string breakeven = JsonSection(json, "breakeven");
   string trailing = JsonSection(json, "trailing");
   string locks = JsonSection(json, "profit_locks");
   cfg.initial_sl_usd_001_lot = JsonNumber(risk, "initial_sl_usd_001_lot", cfg.initial_sl_usd_001_lot);
   cfg.hard_loss_cap_usd_001_lot = JsonNumber(risk, "hard_loss_cap_usd_001_lot", cfg.hard_loss_cap_usd_001_lot);
   cfg.max_floating_loss_usd_001_lot = JsonNumber(risk, "max_floating_loss_usd_001_lot", cfg.max_floating_loss_usd_001_lot);
   cfg.emergency_close = JsonBool(risk, "emergency_close", cfg.emergency_close);
   cfg.breakeven_enable = JsonBool(breakeven, "enable", cfg.breakeven_enable);
   cfg.breakeven_trigger_usd_001_lot = JsonNumber(breakeven, "trigger_usd_001_lot", cfg.breakeven_trigger_usd_001_lot);
   cfg.breakeven_offset_usd_001_lot = JsonNumber(breakeven, "offset_usd_001_lot", cfg.breakeven_offset_usd_001_lot);
   cfg.minimum_hold_seconds_before_be = (int)JsonNumber(breakeven, "minimum_hold_seconds_before_be", JsonNumber(breakeven, "delay_seconds", cfg.minimum_hold_seconds_before_be));
   cfg.minimum_noise_safe_be_usd = JsonNumber(breakeven, "minimum_noise_safe_be_usd", cfg.minimum_noise_safe_be_usd);
   cfg.atr_be_enabled = JsonBool(breakeven, "atr_be_enabled", cfg.atr_be_enabled);
   cfg.atr_be_multiplier = JsonNumber(breakeven, "atr_be_multiplier", cfg.atr_be_multiplier);
   cfg.max_spread_points = JsonNumber(breakeven, "max_spread_points", cfg.max_spread_points);
   cfg.runner_be = JsonBool(breakeven, "runner_be", cfg.runner_be);
   cfg.trailing_enable = JsonBool(trailing, "enable", JsonBool(trailing, "dynamic_trail", cfg.trailing_enable));
   cfg.trailing_start_usd_001_lot = JsonNumber(trailing, "start_usd_001_lot", cfg.trailing_start_usd_001_lot);
   cfg.trailing_distance_usd_001_lot = JsonNumber(trailing, "distance_usd_001_lot", cfg.trailing_distance_usd_001_lot);
   cfg.trailing_step_usd_001_lot = JsonNumber(trailing, "step_usd_001_lot", cfg.trailing_step_usd_001_lot);
   cfg.atr_trail_enable = JsonBool(trailing, "atr_trail", cfg.atr_trail_enable);
   cfg.profit_lock_enable = JsonBool(locks, "enable", cfg.profit_lock_enable);
   string lock1 = JsonSection(locks, "lock_level_1_usd_001_lot");
   cfg.lock1_trigger = JsonNumber(lock1, "trigger", cfg.lock1_trigger);
   cfg.lock1_lock = JsonNumber(lock1, "lock", cfg.lock1_lock);
   cfg.lock2_trigger = JsonNumber(json, "lock2_trigger", cfg.lock2_trigger);
   cfg.lock2_lock = JsonNumber(json, "lock2_lock", cfg.lock2_lock);
   cfg.lock3_trigger = JsonNumber(json, "lock3_trigger", cfg.lock3_trigger);
   cfg.lock3_lock = JsonNumber(json, "lock3_lock", cfg.lock3_lock);
   cfg.minimum_locked_profit_usd_001_lot = JsonNumber(json, "minimum_locked_profit_usd_001_lot", cfg.minimum_locked_profit_usd_001_lot);
   cfg.fixed_take_profit_enable = JsonBool(json, "fixed_take_profit_enable", cfg.fixed_take_profit_enable);
   cfg.fixed_take_profit_close_usd_001_lot = JsonNumber(json, "close_profit_usd_001_lot", cfg.fixed_take_profit_close_usd_001_lot);
   cfg.runner_enable = JsonBool(json, "enable_runner", cfg.runner_enable);
   cfg.runner_timeout_seconds = (int)JsonNumber(json, "runner_timeout_seconds", cfg.runner_timeout_seconds);
   cfg.runner_sl_usd_001_lot = JsonNumber(json, "runner_sl_usd_001_lot", cfg.runner_sl_usd_001_lot);
   cfg.runner_trail = JsonString(json, "runner_trail", cfg.runner_trail);
   cfg.momentum_confirmation = JsonBool(json, "momentum_confirmation", cfg.momentum_confirmation);
   cfg.time_exit_enable = JsonBool(json, "time_exit_enable", cfg.time_exit_enable);
   cfg.maximum_seconds = (int)JsonNumber(json, "maximum_seconds", cfg.maximum_seconds);
   cfg.maximum_bars = (int)JsonNumber(json, "maximum_bars", cfg.maximum_bars);
   cfg.partial_enable = JsonBool(json, "partial_exits_enable", cfg.partial_enable);
   cfg.partial_level_1_percent = (int)JsonNumber(json, "partial_level_1_percent", cfg.partial_level_1_percent);
   cfg.partial_level_2_percent = (int)JsonNumber(json, "partial_level_2_percent", cfg.partial_level_2_percent);
   cfg.remaining_runner_percent = (int)JsonNumber(json, "remaining_runner_percent", cfg.remaining_runner_percent);
   ValidateConfig(cfg);
}

bool LoadDashboardProfile()
{
   ApplyBackwardCompatibleDefaults(g_cfg);
   string dashboard = ReadCommonFile(InpDashboardJsonFile);
   if(dashboard != "")
   {
      OverlayJson(g_cfg, dashboard);
      g_cfg.load_status = "loaded dashboard json";
      g_cfg.fallback_defaults_used = false;
   }
   string profile_file = InpProfilesFolder + "\\" + g_cfg.active_profile + ".json";
   string profile = ReadCommonFile(profile_file);
   if(profile != "")
   {
      OverlayJson(g_cfg, profile);
      g_cfg.load_status = "loaded dashboard + profile json";
      g_cfg.fallback_defaults_used = false;
   }
   g_last_load = TimeCurrent();
   return !g_cfg.fallback_defaults_used;
}

string DashboardJson()
{
   ValidateConfig(g_cfg);
   return StringFormat("{\n"
                       "  \"schema_version\": \"%s\",\n"
                       "  \"active_profile\": \"%s\",\n"
                       "  \"enabled\": %s,\n"
                       "  \"risk\": {\"initial_sl_usd_001_lot\": %.2f, \"hard_loss_cap_usd_001_lot\": %.2f, \"max_floating_loss_usd_001_lot\": %.2f, \"emergency_close\": %s},\n"
                       "  \"breakeven\": {\"enable\": %s, \"trigger_usd_001_lot\": %.2f, \"offset_usd_001_lot\": %.2f, \"minimum_hold_seconds_before_be\": %d, \"minimum_noise_safe_be_usd\": %.2f, \"atr_be_enabled\": %s, \"atr_be_multiplier\": %.2f, \"max_spread_points\": %.2f, \"runner_be\": %s},\n"
                       "  \"trailing\": {\"enable\": %s, \"start_usd_001_lot\": %.2f, \"distance_usd_001_lot\": %.2f, \"step_usd_001_lot\": %.2f, \"atr_trail\": %s, \"dynamic_trail\": %s},\n"
                       "  \"profit_locks\": {\"enable\": %s, \"lock_level_1_usd_001_lot\": {\"trigger\": %.2f, \"lock\": %.2f}, \"lock2_trigger\": %.2f, \"lock2_lock\": %.2f, \"lock3_trigger\": %.2f, \"lock3_lock\": %.2f, \"minimum_locked_profit_usd_001_lot\": %.2f},\n"
                       "  \"fixed_take_profit\": {\"fixed_take_profit_enable\": %s, \"close_profit_usd_001_lot\": %.2f, \"close_mode\": \"IMMEDIATE_MARKET_CLOSE\"},\n"
                       "  \"runner\": {\"enable_runner\": %s, \"runner_timeout_seconds\": %d, \"runner_trail\": \"%s\", \"runner_sl_usd_001_lot\": %.2f, \"momentum_confirmation\": %s},\n"
                       "  \"time_exits\": {\"time_exit_enable\": %s, \"maximum_seconds\": %d, \"maximum_bars\": %d},\n"
                       "  \"partial_exits\": {\"enable\": %s, \"partial_level_1_percent\": %d, \"partial_level_2_percent\": %d, \"remaining_runner_percent\": %d}\n"
                       "}\n",
                       RP_DASH_SCHEMA, g_cfg.active_profile, g_cfg.enabled ? "true" : "false",
                       g_cfg.initial_sl_usd_001_lot, g_cfg.hard_loss_cap_usd_001_lot, g_cfg.max_floating_loss_usd_001_lot, g_cfg.emergency_close ? "true" : "false",
                       g_cfg.breakeven_enable ? "true" : "false", g_cfg.breakeven_trigger_usd_001_lot, g_cfg.breakeven_offset_usd_001_lot,
                       g_cfg.minimum_hold_seconds_before_be, g_cfg.minimum_noise_safe_be_usd, g_cfg.atr_be_enabled ? "true" : "false",
                       g_cfg.atr_be_multiplier, g_cfg.max_spread_points, g_cfg.runner_be ? "true" : "false",
                       g_cfg.trailing_enable ? "true" : "false", g_cfg.trailing_start_usd_001_lot, g_cfg.trailing_distance_usd_001_lot, g_cfg.trailing_step_usd_001_lot, g_cfg.atr_trail_enable ? "true" : "false", g_cfg.trailing_enable ? "true" : "false",
                       g_cfg.profit_lock_enable ? "true" : "false", g_cfg.lock1_trigger, g_cfg.lock1_lock, g_cfg.lock2_trigger, g_cfg.lock2_lock, g_cfg.lock3_trigger, g_cfg.lock3_lock, g_cfg.minimum_locked_profit_usd_001_lot,
                       g_cfg.fixed_take_profit_enable ? "true" : "false", g_cfg.fixed_take_profit_close_usd_001_lot,
                       g_cfg.runner_enable ? "true" : "false", g_cfg.runner_timeout_seconds, g_cfg.runner_trail, g_cfg.runner_sl_usd_001_lot, g_cfg.momentum_confirmation ? "true" : "false",
                       g_cfg.time_exit_enable ? "true" : "false", g_cfg.maximum_seconds, g_cfg.maximum_bars,
                       g_cfg.partial_enable ? "true" : "false", g_cfg.partial_level_1_percent, g_cfg.partial_level_2_percent, g_cfg.remaining_runner_percent);
}

void SaveDashboardProfile()
{
   string profile_file = InpProfilesFolder + "\\" + g_cfg.active_profile + ".json";
   bool ok1 = WriteCommonFile(InpDashboardJsonFile, DashboardJson());
   bool ok2 = WriteCommonFile(profile_file, DashboardJson());
   g_status = (ok1 && ok2) ? "saved profile json" : "save failed - check Common Files permissions";
}

void CreateButton(const string name, const string text, const int x, const int y, const int w)
{
   ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpChartCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, 20);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void CreateLabel(const string name, const int x, const int y)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, InpChartCorner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
}

string BoolText(const bool value) { return value ? "ON" : "OFF"; }

void DrawControl(const string id, const string label, const string value, const int x, const int y)
{
   CreateLabel(RP_PREFIX + "LBL_" + id, x, y + 3);
   ObjectSetString(0, RP_PREFIX + "LBL_" + id, OBJPROP_TEXT, label + ": " + value);
   CreateButton(RP_PREFIX + "MINUS_" + id, "-", x + 178, y, 24);
   CreateButton(RP_PREFIX + "PLUS_" + id, "+", x + 204, y, 24);
}

void DrawDashboard()
{
   ObjectsDeleteAll(0, RP_PREFIX);
   CreateLabel(RP_PREFIX + "TITLE", InpX, InpY);
   CreateButton(RP_PREFIX + "APPLY", "Apply Runtime", InpX, InpY + 22, 112);
   CreateButton(RP_PREFIX + "SAVE", "Save JSON", InpX + 116, InpY + 22, 88);
   CreateButton(RP_PREFIX + "LOAD", "Reload JSON", InpX + 208, InpY + 22, 96);
   CreateButton(RP_PREFIX + "RESET", "Reset Default", InpX + 308, InpY + 22, 100);
   CreateButton(RP_PREFIX + "PROFILE", "Cycle Profile", InpX + 412, InpY + 22, 104);
   CreateButton(RP_PREFIX + "TOGGLE", g_cfg.enabled ? "Disable TM" : "Enable TM", InpX + 520, InpY + 22, 90);

   int y = InpY + 50;
   DrawControl("INITIAL_SL", "Risk Initial SL", DoubleToString(g_cfg.initial_sl_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("HARD_CAP", "Risk Hard Loss Cap", DoubleToString(g_cfg.hard_loss_cap_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("FLOAT_CAP", "Risk Max Floating Loss", DoubleToString(g_cfg.max_floating_loss_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("BE_ENABLE", "BE Enable", BoolText(g_cfg.breakeven_enable), InpX, y); y += 22;
   DrawControl("BE_TRIGGER", "BE Trigger", DoubleToString(g_cfg.breakeven_trigger_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("BE_OFFSET", "BE Offset", DoubleToString(g_cfg.breakeven_offset_usd_001_lot, 2), InpX, y); y += 22;
   DrawControl("BE_HOLD", "BE Min Hold Sec", IntegerToString(g_cfg.minimum_hold_seconds_before_be), InpX, y); y += 22;
   DrawControl("BE_NOISE", "BE Noise Floor", DoubleToString(g_cfg.minimum_noise_safe_be_usd, 2), InpX, y); y += 22;
   DrawControl("ATR_BE", "ATR BE", BoolText(g_cfg.atr_be_enabled) + " x" + DoubleToString(g_cfg.atr_be_multiplier, 2), InpX, y); y += 22;
   DrawControl("RUNNER_BE", "Runner BE", BoolText(g_cfg.runner_be), InpX, y); y += 22;

   y = InpY + 50;
   int x2 = InpX + 250;
   DrawControl("TRAIL_ENABLE", "Trail Enable", BoolText(g_cfg.trailing_enable), x2, y); y += 22;
   DrawControl("TRAIL_START", "Trail Start", DoubleToString(g_cfg.trailing_start_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("TRAIL_DIST", "Trail Distance", DoubleToString(g_cfg.trailing_distance_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("TRAIL_STEP", "Trail Step", DoubleToString(g_cfg.trailing_step_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("ATR_TRAIL", "ATR Trail Enable", BoolText(g_cfg.atr_trail_enable), x2, y); y += 22;
   DrawControl("PROFIT_LOCK_ENABLE", "Profit Lock Enable", BoolText(g_cfg.profit_lock_enable), x2, y); y += 22;
   DrawControl("LOCK1", "Profit Lock L1", DoubleToString(g_cfg.lock1_trigger, 2) + "/" + DoubleToString(g_cfg.lock1_lock, 2), x2, y); y += 22;
   DrawControl("LOCK2", "Profit Lock L2", DoubleToString(g_cfg.lock2_trigger, 2) + "/" + DoubleToString(g_cfg.lock2_lock, 2), x2, y); y += 22;
   DrawControl("LOCK3", "Profit Lock L3", DoubleToString(g_cfg.lock3_trigger, 2) + "/" + DoubleToString(g_cfg.lock3_lock, 2), x2, y); y += 22;
   DrawControl("FIXED_TP", "Fixed TP Close", BoolText(g_cfg.fixed_take_profit_enable) + " @ " + DoubleToString(g_cfg.fixed_take_profit_close_usd_001_lot, 2), x2, y); y += 22;
   DrawControl("MIN_LOCK", "Minimum Locked Profit", DoubleToString(g_cfg.minimum_locked_profit_usd_001_lot, 2), x2, y); y += 22;

   y = InpY + 50;
   int x3 = InpX + 500;
   DrawControl("RUNNER_ENABLE", "Runner Enable", BoolText(g_cfg.runner_enable), x3, y); y += 22;
   DrawControl("RUNNER_TIMEOUT", "Runner Timeout", IntegerToString(g_cfg.runner_timeout_seconds), x3, y); y += 22;
   DrawControl("RUNNER_SL", "Runner SL", DoubleToString(g_cfg.runner_sl_usd_001_lot, 2), x3, y); y += 22;
   DrawControl("MOMENTUM", "Momentum Confirm", BoolText(g_cfg.momentum_confirmation), x3, y); y += 22;
   DrawControl("TIME_ENABLE", "Time Exit Enable", BoolText(g_cfg.time_exit_enable), x3, y); y += 22;
   DrawControl("MAX_SECONDS", "Time Max Seconds", IntegerToString(g_cfg.maximum_seconds), x3, y); y += 22;
   DrawControl("MAX_BARS", "Time Max Bars", IntegerToString(g_cfg.maximum_bars), x3, y); y += 22;
   DrawControl("PARTIAL_ENABLE", "Partial Enable", BoolText(g_cfg.partial_enable), x3, y); y += 22;
   DrawControl("PARTIAL1", "Partial Level 1", IntegerToString(g_cfg.partial_level_1_percent) + "%", x3, y); y += 22;
   DrawControl("PARTIAL2", "Partial Level 2", IntegerToString(g_cfg.partial_level_2_percent) + "%", x3, y); y += 22;
   DrawControl("REMAIN_RUNNER", "Remaining Runner %", IntegerToString(g_cfg.remaining_runner_percent) + "%", x3, y); y += 22;

   CreateLabel(RP_PREFIX + "BODY", InpX, InpY + 292);
   CreateLabel(RP_PREFIX + "BE_KPI", InpX, InpY + 372);
   CreateLabel(RP_PREFIX + "POSITIONS", InpX, InpY + 438);
   UpdateDashboardText();
}

string CurrentProfitLockLevel()
{
   return StringFormat("L1 %.2f/%.2f | L2 %.2f/%.2f | L3 %.2f/%.2f", g_cfg.lock1_trigger, g_cfg.lock1_lock, g_cfg.lock2_trigger, g_cfg.lock2_lock, g_cfg.lock3_trigger, g_cfg.lock3_lock);
}


string BeRollingKpiLine(const int window)
{
   int handle = FileOpen(InpTradeStatisticsCsv, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return StringFormat("BE KPI last %d: no completed-trade evidence yet", window);

   string rows[];
   while(!FileIsEnding(handle))
   {
      string line = FileReadString(handle);
      if(line == "" || StringFind(line, "Ticket,") == 0) continue;
      int n = ArraySize(rows);
      ArrayResize(rows, n + 1);
      rows[n] = line;
   }
   FileClose(handle);

   int start = MathMax(0, ArraySize(rows) - window);
   int be_triggers = 0, be_stop_outs = 0, be_false = 0, survival_count = 0, lost_count = 0, capture_count = 0;
   double lost_sum = 0.0, capture_sum = 0.0, survival_sum = 0.0;
   double survival_values[];

   for(int i = start; i < ArraySize(rows); ++i)
   {
      string cols[];
      int col_count = StringSplit(rows[i], ',', cols);
      if(col_count < 34) continue;
      int be_count = (int)StringToInteger(cols[16]);
      bool triggered = be_count > 0;
      if(!triggered) continue;
      be_triggers += be_count;
      string stopped_text = cols[23];
      string false_text = cols[29];
      StringToLower(stopped_text);
      StringToLower(false_text);
      bool stopped = StringFind(stopped_text, "true") >= 0 || cols[23] == "1";
      bool false_trigger = StringFind(false_text, "true") >= 0 || cols[29] == "1";
      double lost = StringToDouble(cols[28]);
      double survival = StringToDouble(cols[32]);
      double capture = StringToDouble(cols[33]);
      if(stopped) be_stop_outs++;
      if(false_trigger) be_false++;
      lost_sum += lost; lost_count++;
      capture_sum += capture; capture_count++;
      if(survival > 0.0)
      {
         survival_sum += survival; survival_count++;
         int n = ArraySize(survival_values);
         ArrayResize(survival_values, n + 1);
         survival_values[n] = survival;
      }
   }

   ArraySort(survival_values);
   double median = 0.0;
   int surv_n = ArraySize(survival_values);
   if(surv_n > 0)
      median = (surv_n % 2 == 1) ? survival_values[surv_n / 2] : (survival_values[surv_n / 2 - 1] + survival_values[surv_n / 2]) / 2.0;

   return StringFormat("BE KPI last %d: triggers=%d stop-outs=%d stop-rate=%.1f%% false-rate=%.1f%% avg-lost=%.2f avg-capture=%.2f avg-survival=%.0fs median-survival=%.0fs",
                       window, be_triggers, be_stop_outs,
                       be_triggers > 0 ? 100.0 * be_stop_outs / be_triggers : 0.0,
                       be_stop_outs > 0 ? 100.0 * be_false / be_stop_outs : 0.0,
                       lost_count > 0 ? lost_sum / lost_count : 0.0,
                       capture_count > 0 ? capture_sum / capture_count : 0.0,
                       survival_count > 0 ? survival_sum / survival_count : 0.0,
                       median);
}

void UpdateDashboardText()
{
   ObjectSetString(0, RP_PREFIX + "TITLE", OBJPROP_TEXT, "V27.3 Exit Optimization Dashboard (POST-ENTRY ONLY; AI decision engine frozen)");
   string json_status = g_cfg.fallback_defaults_used ? "FALLBACK_EMBEDDED_DEFAULTS" : "JSON_PROFILE_LOADED";
   ObjectSetString(0, RP_PREFIX + "BODY", OBJPROP_TEXT,
                   StringFormat("Profile: %s | JSON Status: %s | Last Reload: %s | TM: %s | Status: %s\nActive Exit Authority Owner: %s | Effective Management Mode: %s\nCurrent BE Trigger: %.2f (effective %.2f; hold %ds) | Trail Distance: %.2f | Hard Loss Cap: %.2f | Profit Lock: %s\nExecutor consumes this runtime profile through Exit Authority priority: EMERGENCY > HARD_LOSS > PROFIT_LOCK > BE > TRAIL > RUNNER > TIME",
                                g_cfg.active_profile, json_status, TimeToString(g_last_load, TIME_DATE | TIME_SECONDS),
                                g_cfg.enabled ? "ENABLED" : "DISABLED", g_status,
                                "Exit Authority Manager (single-owner priority)", g_cfg.runner_enable ? "RUNNER/TRAIL/LOCK" : "SCALP_PROTECTION",
                                g_cfg.breakeven_trigger_usd_001_lot, EffectiveBeTriggerUsd001Lot(), g_cfg.minimum_hold_seconds_before_be, g_cfg.trailing_distance_usd_001_lot, g_cfg.hard_loss_cap_usd_001_lot, CurrentProfitLockLevel()));

   ObjectSetString(0, RP_PREFIX + "BE_KPI", OBJPROP_TEXT, BeRollingKpiLine(20) + "\n" + BeRollingKpiLine(50) + "\n" + BeRollingKpiLine(100));

   string pos = "Open positions (ticket dir lot profit MFE mode owner state profile):\n";
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket) || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);
      double profit = PositionGetDouble(POSITION_PROFIT);
      string owner = "NONE";
      if(profit <= -g_cfg.hard_loss_cap_usd_001_lot * (volume / 0.01)) owner = "HARD_LOSS_CAP";
      else if(profit >= g_cfg.lock1_trigger * (volume / 0.01)) owner = "PROFIT_LOCK";
      else if(g_cfg.breakeven_enable && profit >= g_cfg.breakeven_trigger_usd_001_lot * (volume / 0.01)) owner = "BREAKEVEN";
      else if(g_cfg.fixed_take_profit_enable && profit >= g_cfg.fixed_take_profit_close_usd_001_lot * (volume / 0.01)) owner = "FIXED_TAKE_PROFIT";
      else if(g_cfg.trailing_enable && profit >= g_cfg.trailing_start_usd_001_lot * (volume / 0.01)) owner = "TRAILING";
      else if(g_cfg.runner_enable) owner = "RUNNER";
      pos += StringFormat("%I64u %s %.2f %.2f %.2f %s %s %s %s\n", ticket, type == POSITION_TYPE_BUY ? "BUY" : "SELL", volume, profit, profit, g_cfg.runner_enable ? "RUNNER/TRAIL" : "PROTECT", owner, g_cfg.enabled ? "ACTIVE" : "DISABLED", g_cfg.active_profile);
   }
   ObjectSetString(0, RP_PREFIX + "POSITIONS", OBJPROP_TEXT, pos);
}

void AdjustControl(const string id, const int dir)
{
   double step = 0.05;
   if(id == "INITIAL_SL") g_cfg.initial_sl_usd_001_lot += dir * step;
   else if(id == "HARD_CAP") g_cfg.hard_loss_cap_usd_001_lot += dir * step;
   else if(id == "FLOAT_CAP") g_cfg.max_floating_loss_usd_001_lot += dir * step;
   else if(id == "BE_ENABLE") g_cfg.breakeven_enable = !g_cfg.breakeven_enable;
   else if(id == "BE_TRIGGER") g_cfg.breakeven_trigger_usd_001_lot += dir * step;
   else if(id == "BE_OFFSET") g_cfg.breakeven_offset_usd_001_lot += dir * step;
   else if(id == "BE_HOLD") g_cfg.minimum_hold_seconds_before_be += dir * 5;
   else if(id == "BE_NOISE") g_cfg.minimum_noise_safe_be_usd += dir * step;
   else if(id == "ATR_BE") g_cfg.atr_be_enabled = !g_cfg.atr_be_enabled;
   else if(id == "RUNNER_BE") g_cfg.runner_be = !g_cfg.runner_be;
   else if(id == "TRAIL_ENABLE") g_cfg.trailing_enable = !g_cfg.trailing_enable;
   else if(id == "TRAIL_START") g_cfg.trailing_start_usd_001_lot += dir * step;
   else if(id == "TRAIL_DIST") g_cfg.trailing_distance_usd_001_lot += dir * step;
   else if(id == "TRAIL_STEP") g_cfg.trailing_step_usd_001_lot += dir * step;
   else if(id == "ATR_TRAIL") g_cfg.atr_trail_enable = !g_cfg.atr_trail_enable;
   else if(id == "PROFIT_LOCK_ENABLE") g_cfg.profit_lock_enable = !g_cfg.profit_lock_enable;
   else if(id == "LOCK1") { g_cfg.lock1_trigger += dir * step; g_cfg.lock1_lock += dir * step; }
   else if(id == "LOCK2") { g_cfg.lock2_trigger += dir * step; g_cfg.lock2_lock += dir * step; }
   else if(id == "LOCK3") { g_cfg.lock3_trigger += dir * step; g_cfg.lock3_lock += dir * step; }
   else if(id == "MIN_LOCK") g_cfg.minimum_locked_profit_usd_001_lot += dir * step;
   else if(id == "RUNNER_ENABLE") g_cfg.runner_enable = !g_cfg.runner_enable;
   else if(id == "RUNNER_TIMEOUT") g_cfg.runner_timeout_seconds += dir * 5;
   else if(id == "RUNNER_SL") g_cfg.runner_sl_usd_001_lot += dir * step;
   else if(id == "MOMENTUM") g_cfg.momentum_confirmation = !g_cfg.momentum_confirmation;
   else if(id == "TIME_ENABLE") g_cfg.time_exit_enable = !g_cfg.time_exit_enable;
   else if(id == "MAX_SECONDS") g_cfg.maximum_seconds += dir * 30;
   else if(id == "MAX_BARS") g_cfg.maximum_bars += dir;
   else if(id == "PARTIAL_ENABLE") g_cfg.partial_enable = !g_cfg.partial_enable;
   else if(id == "PARTIAL1") g_cfg.partial_level_1_percent += dir * 5;
   else if(id == "PARTIAL2") g_cfg.partial_level_2_percent += dir * 5;
   else if(id == "REMAIN_RUNNER") g_cfg.remaining_runner_percent += dir * 5;
   ValidateConfig(g_cfg);
   g_status = "edited in-memory - click Apply and/or Save JSON";
}

void CycleProfile()
{
   if(g_cfg.active_profile == "Profile_A") g_cfg.active_profile = "Profile_B";
   else if(g_cfg.active_profile == "Profile_B") g_cfg.active_profile = "Profile_C";
   else if(g_cfg.active_profile == "Profile_C") g_cfg.active_profile = "Profile_D";
   else g_cfg.active_profile = "Profile_A";
   g_status = "profile selected in-memory - click Reload JSON to load file or Save JSON to create it";
}


double CurrentAtrMoney001Lot()
{
   if(!g_cfg.atr_be_enabled) return 0.0;
   int handle = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(handle == INVALID_HANDLE) return 0.0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(handle, 0, 0, 1, buf) <= 0)
   {
      IndicatorRelease(handle);
      return 0.0;
   }
   IndicatorRelease(handle);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0.0 || tick_size <= 0.0) return 0.0;
   return (buf[0] / tick_size) * tick_value;
}

double EffectiveBeTriggerUsd001Lot()
{
   double trigger = MathMax(g_cfg.breakeven_trigger_usd_001_lot, g_cfg.minimum_noise_safe_be_usd);
   double atr_money = CurrentAtrMoney001Lot();
   if(atr_money > 0.0) trigger = MathMax(trigger, atr_money * g_cfg.atr_be_multiplier);
   return trigger;
}

bool IsSpreadNormal()
{
   if(g_cfg.max_spread_points <= 0.0) return true;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0) return true;
   return ((ask - bid) / point) <= g_cfg.max_spread_points;
}

double MoneyToPriceDistance(const double money_001_lot, const double volume)
{
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0.0 || tick_size <= 0.0 || volume <= 0.0) return 0.0;
   double scaled_money = money_001_lot * (volume / 0.01);
   return (scaled_money / tick_value) * tick_size;
}

void UpdateOpenTradeExcursions()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket) || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      int idx = EnsureTrack(ticket);
      double profit = PositionGetDouble(POSITION_PROFIT);
      double price = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      g_track_position_sl_last[idx] = PositionGetDouble(POSITION_SL);
      g_track_position_tp_last[idx] = PositionGetDouble(POSITION_TP);
      if(profit > g_track_mfe[idx]) { g_track_mfe[idx] = profit; g_track_mfe_time[idx] = TimeCurrent(); g_track_price_at_mfe[idx] = price; }
      if(profit < g_track_mae[idx]) { g_track_mae[idx] = profit; g_track_mae_time[idx] = TimeCurrent(); g_track_price_at_mae[idx] = price; }
      if(g_track_be_enabled[idx])
      {
         if(profit > g_track_max_profit_after_be_trigger[idx])
            g_track_max_profit_after_be_trigger[idx] = profit;
         if(g_track_min_profit_after_be_trigger[idx] == 0.0 || profit < g_track_min_profit_after_be_trigger[idx])
            g_track_min_profit_after_be_trigger[idx] = profit;
      }
   }
}

string TradeStatisticsRelativePath()
{
   string configured = InpTradeStatisticsCsv == "" ? TRADE_STATS_RELATIVE_PATH : InpTradeStatisticsCsv;
   if(StringFind(configured, ":") >= 0 || StringFind(configured, "\\") == 0 || StringFind(configured, "/") == 0)
      return TRADE_STATS_RELATIVE_PATH;
   return configured;
}

string TradeStatisticsResolvedPath()
{
   return TerminalInfoString(TERMINAL_COMMONDATA_PATH) + "\\Files\\" + TradeStatisticsRelativePath();
}

bool EnsureCommonFolder(const string folder)
{
   ResetLastError();
   if(!FolderCreate(folder, FILE_COMMON))
   {
      int err = GetLastError();
      if(err != 5016)
      {
         Print(StringFormat("TRADE_STATS_FOLDER_CREATE_FAILED | folder=%s | error=%d", folder, err));
         return false;
      }
   }
   return true;
}

bool EnsureTradeStatisticsFolders()
{
   if(!EnsureCommonFolder("RP_AI_EA")) return false;
   if(!EnsureCommonFolder("RP_AI_EA\\analysis")) return false;
   if(!EnsureCommonFolder("RP_AI_EA\\analysis\\archive")) return false;
   return true;
}

string CsvEscape(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\"", "\"\"");
   return "\"" + escaped + "\"";
}


string TradeStatisticsHeaderV2735()
{
   return "csv_schema_version,ticket,symbol,direction,trade_mode,entry_time,exit_time,entry_price,exit_price,stop_loss,take_profit,exit_reason,close_source,broker_exit_reason,dashboard_exit_reason,exit_authority_owner,broker_sl_price,broker_tp_price,position_sl_at_close,position_tp_at_close,order_sl_at_open,order_tp_at_open,close_trigger_price,close_trigger_distance_usd,decision_uuid,sequence_id,heartbeat_unix,market_state_age_sec,decision_age_sec,action,bias,mode,bb_state,rsi,macd_hist,adx,atr,spread_points_entry,buy_score,sell_score,score_gap,dominant_direction,execution_state,management_mode,dashboard_profile_at_entry,spread_points_exit,atr_exit,bb_state_exit,rsi_exit,macd_hist_exit,adx_exit,floating_profit_before_close,floating_loss_before_close,position_age_seconds_at_close,dashboard_profile_at_exit,mfe,mae,time_to_mfe_seconds,time_to_mae_seconds,price_at_mfe,price_at_mae,mfe_before_exit,mae_before_exit,max_profit_usd,realized_profit_usd,lost_opportunity_usd,profit_capture_ratio,entry_quality_score,exit_quality_score,trade_quality_score,net_profit,duration,dashboard_profile,be_trigger_count,be_trigger_price,be_trigger_profit,be_trigger_time,be_trigger_age_seconds,be_sl_price,be_offset_usd,be_stop_out,realized_profit,profit_before_be,maximum_profit_after_be,maximum_drawdown_after_be,lost_opportunity_after_be,be_false_trigger,be_false_trigger_distance,be_false_trigger_time,be_survival_time_seconds,capture_ratio_after_be,post_sl_continuation_direction\n";
}

bool IsManualDealReason(const long reason_code)
{
   return reason_code == DEAL_REASON_CLIENT || reason_code == DEAL_REASON_MOBILE || reason_code == DEAL_REASON_WEB;
}

string ClassifyCloseSource(const long reason_code, const double broker_sl, const double broker_tp, const string dashboard_reason)
{
   if(reason_code == DEAL_REASON_SL && broker_sl > 0.0) return "BROKER_SL";
   if(reason_code == DEAL_REASON_TP && broker_tp > 0.0) return "BROKER_TP";
   if(reason_code == DEAL_REASON_EXPERT)
   {
      if(dashboard_reason == "BE") return "DASHBOARD_BE";
      if(dashboard_reason == "TRAIL") return "DASHBOARD_TRAIL";
      if(dashboard_reason == "PROFIT_LOCK") return "DASHBOARD_PROFIT_LOCK";
      if(dashboard_reason == "TIME_EXIT") return "DASHBOARD_TIME_EXIT";
      if(dashboard_reason == "PARTIAL_EXIT") return "DASHBOARD_PARTIAL_EXIT";
      if(dashboard_reason == "MARKET_CLOSE" || dashboard_reason == "HARD_LOSS_CAP") return "DASHBOARD_MARKET_CLOSE";
      return "EXPERT_CLOSE";
   }
   if(IsManualDealReason(reason_code)) return "MANUAL_CLOSE";
   return "UNKNOWN";
}

double QualityScore(const double numerator, const double denominator)
{
   if(denominator <= 0.0) return 0.0;
   return ClampDouble((numerator / denominator) * 100.0, 0.0, 100.0);
}

string TrimCsvLineEnding(string value)
{
   StringReplace(value, "\r", "");
   StringReplace(value, "\n", "");
   return value;
}

int CsvColumnCount(const string line)
{
   int columns = 1;
   bool in_quotes = false;
   for(int i = 0; i < StringLen(line); ++i)
   {
      ushort ch = StringGetCharacter(line, i);
      if(ch == 34)
      {
         if(in_quotes && i + 1 < StringLen(line) && StringGetCharacter(line, i + 1) == 34)
         {
            ++i;
            continue;
         }
         in_quotes = !in_quotes;
      }
      else if(ch == ',' && !in_quotes)
      {
         ++columns;
      }
   }
   return columns;
}

bool IsTradeStatisticsHeaderV2735Compatible(const string header)
{
   string expected = TrimCsvLineEnding(TradeStatisticsHeaderV2735());
   string detected = TrimCsvLineEnding(header);
   return detected == expected && StringFind(detected, "csv_schema_version") == 0 && StringFind(detected, TRADE_STATS_SCHEMA_VERSION) < 0;
}

string TradeStatisticsArchivePath()
{
   MqlDateTime ts;
   TimeToStruct(TimeCurrent(), ts);
   return StringFormat("RP_AI_EA\\analysis\\archive\\trade_statistics_legacy_%04d%02d%02d_%02d%02d%02d.csv", ts.year, ts.mon, ts.day, ts.hour, ts.min, ts.sec);
}

bool CreateFreshTradeStatisticsFile()
{
   string path = TradeStatisticsRelativePath();
   ResetLastError();
   int handle = FileOpen(path, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      int err = GetLastError();
      Print(StringFormat("CSV_HEADER_CREATE_FAILED | path=%s | error=%d", path, err));
      Print(StringFormat("TRADE_STATISTICS_FILE_OPEN_FAILED | path=%s | error=%d", path, err));
      return false;
   }
   FileWriteString(handle, TradeStatisticsHeaderV2735());
   FileClose(handle);
   Print("TRADE_STATS_NEW_SCHEMA_FILE_CREATED");
   Print("CSV_HEADER_READY");
   return true;
}

bool EnsureTradeStatisticsHeader()
{
   Print("TRADE_STATS_SCHEMA_CHECK_START");
   if(!EnsureTradeStatisticsFolders()) return false;
   string path = TradeStatisticsRelativePath();
   ResetLastError();
   int handle = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      int err = GetLastError();
      if(err == 5004 || err == 5019 || err == 5024)
         return CreateFreshTradeStatisticsFile();
      Print(StringFormat("TRADE_STATISTICS_FILE_OPEN_FAILED | path=%s | error=%d", path, err));
      return false;
   }
   if(FileSize(handle) == 0)
   {
      FileClose(handle);
      return CreateFreshTradeStatisticsFile();
   }

   string existing_header = FileReadString(handle);
   FileClose(handle);
   Print(StringFormat("TRADE_STATS_EXISTING_HEADER_DETECTED | header_columns=%d", CsvColumnCount(existing_header)));
   if(IsTradeStatisticsHeaderV2735Compatible(existing_header))
   {
      Print("TRADE_STATS_SCHEMA_COMPATIBLE");
      Print("CSV_HEADER_READY");
      return true;
   }

   Print(StringFormat("TRADE_STATS_SCHEMA_MISMATCH_DETECTED | active_columns=%d | expected_columns=%d", CsvColumnCount(existing_header), CsvColumnCount(TradeStatisticsHeaderV2735())));
   string archive_path = TradeStatisticsArchivePath();
   ResetLastError();
   if(!FileMove(path, FILE_COMMON, archive_path, FILE_COMMON))
   {
      int move_err = GetLastError();
      Print(StringFormat("TRADE_STATS_LEGACY_ARCHIVE_FAILED | source=%s | archive=%s | error=%d", path, archive_path, move_err));
      return false;
   }
   Print(StringFormat("TRADE_STATS_LEGACY_ARCHIVED | archive=%s", archive_path));
   return CreateFreshTradeStatisticsFile();
}

void RecordCompletedTrade(const ulong position_id, const ulong exit_deal)
{
   Print("COMPLETED_TRADE_RECORD_ATTEMPT");
   if(!HistoryDealSelect(exit_deal))
   {
      Print("COMPLETED_TRADE_RECORD_FAILED | reason=history_deal_select_failed");
      return;
   }
   string symbol = HistoryDealGetString(exit_deal, DEAL_SYMBOL);
   if(symbol != _Symbol) return;
   datetime exit_time = (datetime)HistoryDealGetInteger(exit_deal, DEAL_TIME);
   double exit_price = HistoryDealGetDouble(exit_deal, DEAL_PRICE);
   double net_profit = HistoryDealGetDouble(exit_deal, DEAL_PROFIT) + HistoryDealGetDouble(exit_deal, DEAL_SWAP) + HistoryDealGetDouble(exit_deal, DEAL_COMMISSION);
   long reason_code = HistoryDealGetInteger(exit_deal, DEAL_REASON);
   string exit_reason = EnumToString((ENUM_DEAL_REASON)reason_code);

   datetime entry_time = 0;
   double entry_price = 0.0;
   string direction = "UNKNOWN";
   if(HistorySelect(0, exit_time + 60))
   {
      for(int i = HistoryDealsTotal() - 1; i >= 0; --i)
      {
         ulong deal = HistoryDealGetTicket(i);
         if((ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) != position_id) continue;
         if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
         entry_time = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
         entry_price = HistoryDealGetDouble(deal, DEAL_PRICE);
         direction = ((ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE) == DEAL_TYPE_BUY) ? "BUY" : "SELL";
      }
   }

   int idx = TrackIndex(position_id);
   double mfe = idx >= 0 ? g_track_mfe[idx] : MathMax(net_profit, 0.0);
   double mae = idx >= 0 ? g_track_mae[idx] : MathMin(net_profit, 0.0);
   bool be_enabled = idx >= 0 ? g_track_be_enabled[idx] : false;
   double be_trigger_price = idx >= 0 ? g_track_be_trigger_price[idx] : 0.0;
   double be_trigger_profit = idx >= 0 ? g_track_be_trigger_profit_usd[idx] : 0.0;
   datetime be_trigger_time = idx >= 0 ? g_track_be_trigger_time[idx] : 0;
   int be_after_seconds = idx >= 0 ? g_track_be_trigger_after_seconds[idx] : 0;
   double be_sl_price = idx >= 0 ? g_track_be_sl_price[idx] : 0.0;
   double be_offset = idx >= 0 ? g_track_be_offset_usd[idx] : 0.0;
   bool be_stop_out = be_enabled && reason_code == DEAL_REASON_SL;
   double profit_before_be_stop_out = be_stop_out ? be_trigger_profit : 0.0;
   double max_profit_after_be = idx >= 0 ? g_track_max_profit_after_be_trigger[idx] : 0.0;
   double min_profit_after_be = idx >= 0 ? g_track_min_profit_after_be_trigger[idx] : 0.0;
   double maximum_drawdown_after_be = be_enabled ? MathMin(0.0, min_profit_after_be - be_trigger_profit) : 0.0;
   double lost_opportunity_after_be = be_stop_out ? MathMax(0.0, max_profit_after_be - net_profit) : 0.0;
   double false_distance = be_stop_out ? MathMax(0.0, max_profit_after_be - be_trigger_profit - InpBeFalseTriggerThresholdUsd) : 0.0;
   bool be_false_trigger = false_distance > 0.0;
   int be_survival_seconds = (be_stop_out && be_trigger_time > 0) ? (int)(exit_time - be_trigger_time) : 0;
   double capture_ratio_after_be = (be_enabled && max_profit_after_be > 0.0) ? net_profit / max_profit_after_be : 0.0;

   double broker_sl_price = idx >= 0 ? g_track_order_sl_at_open[idx] : 0.0;
   double broker_tp_price = idx >= 0 ? g_track_order_tp_at_open[idx] : 0.0;
   double position_sl_at_close = idx >= 0 ? g_track_position_sl_last[idx] : 0.0;
   double position_tp_at_close = idx >= 0 ? g_track_position_tp_last[idx] : 0.0;
   double order_sl_at_open = idx >= 0 ? g_track_order_sl_at_open[idx] : 0.0;
   double order_tp_at_open = idx >= 0 ? g_track_order_tp_at_open[idx] : 0.0;
   string dashboard_reason = idx >= 0 ? g_track_dashboard_close_intent[idx] : "";
   string close_source = ClassifyCloseSource(reason_code, broker_sl_price, broker_tp_price, dashboard_reason);
   string exit_owner = close_source == "UNKNOWN" ? "UNKNOWN" : (StringFind(close_source, "DASHBOARD_") == 0 ? "DASHBOARD" : (StringFind(close_source, "BROKER_") == 0 ? "BROKER" : (close_source == "MANUAL_CLOSE" ? "MANUAL" : "EXPERT")));
   double close_trigger_price = exit_price;
   double trigger_ref = 0.0;
   if(close_source == "BROKER_SL") trigger_ref = broker_sl_price;
   else if(close_source == "BROKER_TP") trigger_ref = broker_tp_price;
   else if(position_sl_at_close > 0.0) trigger_ref = position_sl_at_close;
   double close_trigger_distance_usd = trigger_ref > 0.0 ? MathAbs(exit_price - trigger_ref) : 0.0;
   double max_profit_usd = MathMax(0.0, mfe);
   double realized_profit_usd = net_profit;
   double lost_opportunity_usd = max_profit_usd - realized_profit_usd;
   double profit_capture_ratio = max_profit_usd > 0.0 ? realized_profit_usd / max_profit_usd : 0.0;
   double entry_quality_score = (mfe <= 0.0) ? 0.0 : QualityScore(mfe, mfe + MathAbs(mae));
   double exit_quality_score = QualityScore(MathMax(0.0, realized_profit_usd), max_profit_usd);
   double trade_quality_score = (entry_quality_score * 0.45) + (exit_quality_score * 0.55);
   int time_to_mfe_seconds = (idx >= 0 && g_track_mfe_time[idx] > 0 && entry_time > 0) ? (int)(g_track_mfe_time[idx] - entry_time) : 0;
   int time_to_mae_seconds = (idx >= 0 && g_track_mae_time[idx] > 0 && entry_time > 0) ? (int)(g_track_mae_time[idx] - entry_time) : 0;
   string exit_json = ReadCommonFile(MARKET_STATE_JSON_FILE);
   double spread_points_exit = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   double atr_exit = JsonNumber(exit_json, "atr", 0.0);
   string bb_state_exit = JsonString(exit_json, "bb_state", "");
   double rsi_exit = JsonNumber(exit_json, "rsi", 0.0);
   double macd_hist_exit = JsonNumber(exit_json, "macd_hist", 0.0);
   double adx_exit = JsonNumber(exit_json, "adx", 0.0);
   double floating_profit_before_close = MathMax(net_profit, 0.0);
   double floating_loss_before_close = MathMin(net_profit, 0.0);
   int position_age_seconds_at_close = (entry_time > 0) ? (int)(exit_time - entry_time) : 0;

   if(close_source == "UNKNOWN")
      Print(StringFormat("EXIT_SOURCE_UNKNOWN | ticket=%I64u | reason=broker_reason=%s dashboard_reason=%s", position_id, exit_reason, dashboard_reason));
   Print(StringFormat("EXIT_SOURCE_CLASSIFIED | ticket=%I64u | close_source=%s | broker_reason=%s | dashboard_reason=%s", position_id, close_source, exit_reason, dashboard_reason));
   if(!EnsureTradeStatisticsHeader())
   {
      Print(StringFormat("COMPLETED_TRADE_RECORD_FAILED | reason=header_file_open_failed | error=%d", GetLastError()));
      return;
   }
   string path = TradeStatisticsRelativePath();
   ResetLastError();
   int handle = FileOpen(path, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      int err = GetLastError();
      Print(StringFormat("COMPLETED_TRADE_RECORD_FAILED | reason=file_open_failed | error=%d", err));
      return;
   }
   FileSeek(handle, 0, SEEK_END);
   string be_stop_out_text = (be_stop_out ? "true" : "false");
   string be_false_trigger_text = (be_false_trigger ? "true" : "false");
   string row = StringFormat("%s,%I64u,%s,%s,%s,%s,%s,%.5f,%.5f,%.5f,%.5f,%s,%s,%s,%s,%s,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%s,%.0f,%.0f,%.2f,%.2f,%s,%s,%s,%s,%.2f,%.5f,%.2f,%.5f,%.2f,%.2f,%.2f,%.2f,%s,%s,%s,%s,%.2f,%.5f,%s,%.2f,%.5f,%.2f,%.2f,%.2f,%d,%s,",
      TRADE_STATS_SCHEMA_VERSION, position_id, CsvEscape(symbol), CsvEscape(direction), CsvEscape(g_cfg.runner_enable ? "RUNNER/TRAIL" : "PROTECT"),
      CsvEscape(TimeToString(entry_time, TIME_DATE | TIME_SECONDS)), CsvEscape(TimeToString(exit_time, TIME_DATE | TIME_SECONDS)),
      entry_price, exit_price, position_sl_at_close, position_tp_at_close, CsvEscape(exit_reason), CsvEscape(close_source), CsvEscape(exit_reason), CsvEscape(dashboard_reason), CsvEscape(exit_owner),
      broker_sl_price, broker_tp_price, position_sl_at_close, position_tp_at_close, order_sl_at_open, order_tp_at_open, close_trigger_price, close_trigger_distance_usd,
      CsvEscape(idx >= 0 ? g_track_decision_uuid[idx] : ""), idx >= 0 ? g_track_sequence_id[idx] : 0.0, idx >= 0 ? g_track_heartbeat_unix[idx] : 0.0, idx >= 0 ? g_track_market_state_age_sec[idx] : 0.0, idx >= 0 ? g_track_decision_age_sec[idx] : 0.0,
      CsvEscape(idx >= 0 ? g_track_action[idx] : ""), CsvEscape(idx >= 0 ? g_track_bias[idx] : ""), CsvEscape(idx >= 0 ? g_track_mode[idx] : ""), CsvEscape(idx >= 0 ? g_track_bb_state[idx] : ""), idx >= 0 ? g_track_rsi[idx] : 0.0, idx >= 0 ? g_track_macd_hist[idx] : 0.0, idx >= 0 ? g_track_adx[idx] : 0.0, idx >= 0 ? g_track_atr[idx] : 0.0,
      idx >= 0 ? g_track_spread_points_entry[idx] : 0.0, idx >= 0 ? g_track_buy_score[idx] : 0.0, idx >= 0 ? g_track_sell_score[idx] : 0.0, idx >= 0 ? g_track_score_gap[idx] : 0.0,
      CsvEscape(idx >= 0 ? g_track_dominant_direction[idx] : ""), CsvEscape(idx >= 0 ? g_track_execution_state[idx] : ""), CsvEscape(idx >= 0 ? g_track_management_mode[idx] : ""), CsvEscape(idx >= 0 ? g_track_dashboard_profile_at_entry[idx] : ""),
      spread_points_exit, atr_exit, CsvEscape(bb_state_exit), rsi_exit, macd_hist_exit, adx_exit, floating_profit_before_close, floating_loss_before_close, position_age_seconds_at_close, CsvEscape(g_cfg.active_profile));
   row += StringFormat("%.2f,%.2f,%d,%d,%.5f,%.5f,%.2f,%.2f,%.2f,%.2f,%.2f,%.4f,%.2f,%.2f,%.2f,%.2f,%d,%s,%d,%.5f,%.2f,%s,%d,%.5f,%.2f,%s,%.2f,%.2f,%.2f,%.2f,%.2f,%s,%.2f,%s,%d,%.4f\n",
      mfe, mae, time_to_mfe_seconds, time_to_mae_seconds, idx >= 0 ? g_track_price_at_mfe[idx] : 0.0, idx >= 0 ? g_track_price_at_mae[idx] : 0.0, mfe, mae,
      max_profit_usd, realized_profit_usd, lost_opportunity_usd, profit_capture_ratio, entry_quality_score, exit_quality_score, trade_quality_score, net_profit, (int)(exit_time - entry_time), CsvEscape(g_cfg.active_profile),
      be_enabled ? 1 : 0, be_trigger_price, be_trigger_profit, CsvEscape(be_trigger_time > 0 ? TimeToString(be_trigger_time, TIME_DATE | TIME_SECONDS) : ""),
      be_after_seconds, be_sl_price, be_offset, be_stop_out_text, net_profit, profit_before_be_stop_out, max_profit_after_be, maximum_drawdown_after_be, lost_opportunity_after_be,
      be_false_trigger_text, false_distance, CsvEscape(be_false_trigger ? TimeToString(exit_time, TIME_DATE | TIME_SECONDS) : ""), be_survival_seconds, capture_ratio_after_be);
   row = StringSubstr(row, 0, StringLen(row) - 1) + ",\"\"\n";
   int row_columns = CsvColumnCount(row);
   int header_columns = CsvColumnCount(TradeStatisticsHeaderV2735());
   if(row_columns == header_columns)
      Print(StringFormat("TRADE_STATS_ROW_COLUMN_COUNT_PASS | ticket=%I64u | columns=%d", position_id, row_columns));
   else
      Print(StringFormat("TRADE_STATS_ROW_COLUMN_COUNT_FAIL | ticket=%I64u | row_columns=%d | header_columns=%d", position_id, row_columns, header_columns));
   FileWriteString(handle, row);
   FileClose(handle);
   Print(StringFormat("COMPLETED_TRADE_RECORDED | ticket=%I64u | pnl=%.2f | profile=%s | close_source=%s | exit_quality=%.2f | schema_version=%s", position_id, net_profit, g_cfg.active_profile, close_source, exit_quality_score, TRADE_STATS_SCHEMA_VERSION));
   RemoveTrack(position_id);
}

void ManageOpenPositions()
{
   UpdateOpenTradeExcursions();
   if(!InpManageOpenTrades || !g_cfg.enabled) return;
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket) || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double profit = PositionGetDouble(POSITION_PROFIT);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double price = (type == POSITION_TYPE_BUY) ? bid : ask;

      if(profit <= -g_cfg.hard_loss_cap_usd_001_lot * (volume / 0.01))
      {
         g_track_dashboard_close_intent[EnsureTrack(ticket)] = "HARD_LOSS_CAP";
         g_trade.PositionClose(ticket);
         continue;
      }

      if(g_cfg.fixed_take_profit_enable && profit >= g_cfg.fixed_take_profit_close_usd_001_lot * (volume / 0.01))
      {
         g_track_dashboard_close_intent[EnsureTrack(ticket)] = "MARKET_CLOSE";
         g_trade.PositionClose(ticket);
         continue;
      }

      double candidate_sl = sl;
      double scale = volume / 0.01;
      double lock_money = -999999.0;
      if(g_cfg.profit_lock_enable)
      {
         if(profit >= g_cfg.lock3_trigger * scale) lock_money = MathMax(lock_money, g_cfg.lock3_lock);
         else if(profit >= g_cfg.lock2_trigger * scale) lock_money = MathMax(lock_money, g_cfg.lock2_lock);
         else if(profit >= g_cfg.lock1_trigger * scale) lock_money = MathMax(lock_money, g_cfg.lock1_lock);
         if(lock_money > -999998.0)
         {
            g_track_dashboard_close_intent[EnsureTrack(ticket)] = "PROFIT_LOCK";
            lock_money = MathMax(lock_money, g_cfg.minimum_locked_profit_usd_001_lot);
            double lock_dist = MoneyToPriceDistance(lock_money, volume);
            candidate_sl = (type == POSITION_TYPE_BUY) ? open + lock_dist : open - lock_dist;
         }
      }
      if(g_cfg.breakeven_enable)
      {
         int idx = EnsureTrack(ticket);
         datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
         int open_seconds = (int)(TimeCurrent() - open_time);
         double be_trigger = EffectiveBeTriggerUsd001Lot();
         bool hold_ok = open_seconds >= g_cfg.minimum_hold_seconds_before_be;
         bool profit_ok = profit >= be_trigger * scale;
         bool spread_ok = IsSpreadNormal();
         if(!g_track_be_enabled[idx] && hold_ok && profit_ok && spread_ok)
         {
            double be_dist = MoneyToPriceDistance(g_cfg.breakeven_offset_usd_001_lot, volume);
            candidate_sl = (type == POSITION_TYPE_BUY) ? open + be_dist : open - be_dist;
            g_track_dashboard_close_intent[idx] = "BE";
            g_track_be_enabled[idx] = true;
            g_track_be_trigger_price[idx] = price;
            g_track_be_trigger_profit_usd[idx] = profit;
            g_track_be_trigger_time[idx] = TimeCurrent();
            g_track_be_trigger_after_seconds[idx] = open_seconds;
            g_track_be_sl_price[idx] = candidate_sl;
            g_track_be_offset_usd[idx] = g_cfg.breakeven_offset_usd_001_lot;
            g_track_max_profit_after_be_trigger[idx] = profit;
            g_track_min_profit_after_be_trigger[idx] = profit;
            Print(StringFormat("NOISE_SAFE_BE_TRIGGER ticket=%I64u profit=%.2f trigger=%.2f hold=%d spread_ok=%s sl=%.5f", ticket, profit, be_trigger * scale, open_seconds, spread_ok ? "true" : "false", candidate_sl));
         }
      }
      if(g_cfg.trailing_enable && profit >= g_cfg.trailing_start_usd_001_lot * (volume / 0.01))
      {
         g_track_dashboard_close_intent[EnsureTrack(ticket)] = "TRAIL";
         double trail_dist = MoneyToPriceDistance(g_cfg.trailing_distance_usd_001_lot, volume);
         double trail_sl = (type == POSITION_TYPE_BUY) ? price - trail_dist : price + trail_dist;
         if(candidate_sl == 0.0 || (type == POSITION_TYPE_BUY && trail_sl > candidate_sl) || (type == POSITION_TYPE_SELL && trail_sl < candidate_sl))
            candidate_sl = trail_sl;
      }
      if(candidate_sl != sl && candidate_sl > 0.0)
      {
         if(IsTpOnlyProfileActive())
         {
            Print("POSITIONMODIFY_BLOCKED_BY_TP_ONLY_PROFILE");
            continue;
         }
         g_trade.PositionModify(ticket, NormalizeDouble(candidate_sl, _Digits), tp);
      }
   }
}

int OnInit()
{
   LoadDashboardProfile();
   Print("DASHBOARD_SINGLE_SOURCE_OF_TRUTH_PASS");
   Print(StringFormat("TRADE_STATS_SCHEMA_VERSION = %s", TRADE_STATS_SCHEMA_VERSION));
   Print("TRADE_STATS_EXIT_AUDIT_ENABLED = true");
   Print("TRADE_STATS_ENTRY_SNAPSHOT_ENABLED = true");
   Print("TRADE_STATS_EXIT_SNAPSHOT_ENABLED = true");
   Print("TRADE_STATISTICS_OUTPUT_MODE = FILE_COMMON");
   Print(StringFormat("TRADE_STATISTICS_RELATIVE_PATH = %s", TradeStatisticsRelativePath()));
   Print(StringFormat("TRADE_STATISTICS_CSV_PATH = %s", TradeStatisticsResolvedPath()));
   if(EnsureTradeStatisticsHeader())
      Print("FILE_WRITE_PERMISSION_PASS");
   DrawDashboard();
   EventSetTimer(MathMax(1, InpTimerSeconds));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, RP_PREFIX);
}

void OnTimer()
{
   ManageOpenPositions();
   UpdateDashboardText();
}

void OnTick()
{
   ManageOpenPositions();
}

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY) == DEAL_ENTRY_OUT)
      RecordCompletedTrade((ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID), trans.deal);
}

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK) return;
   if(sparam == RP_PREFIX + "SAVE") SaveDashboardProfile();
   else if(sparam == RP_PREFIX + "LOAD") { LoadDashboardProfile(); g_status = "reloaded json without recompiling"; }
   else if(sparam == RP_PREFIX + "APPLY") { ValidateConfig(g_cfg); g_status = "applied runtime values immediately"; ManageOpenPositions(); }
   else if(sparam == RP_PREFIX + "RESET") { ApplyBackwardCompatibleDefaults(g_cfg); ValidateConfig(g_cfg); g_status = "reset to embedded defaults in-memory"; }
   else if(sparam == RP_PREFIX + "PROFILE") CycleProfile();
   else if(sparam == RP_PREFIX + "TOGGLE") { g_cfg.enabled = !g_cfg.enabled; g_status = g_cfg.enabled ? "trade management enabled" : "trade management disabled"; }
   else if(StringFind(sparam, RP_PREFIX + "PLUS_") == 0) AdjustControl(StringSubstr(sparam, StringLen(RP_PREFIX + "PLUS_")), 1);
   else if(StringFind(sparam, RP_PREFIX + "MINUS_") == 0) AdjustControl(StringSubstr(sparam, StringLen(RP_PREFIX + "MINUS_")), -1);
   DrawDashboard();
}
//+------------------------------------------------------------------+
