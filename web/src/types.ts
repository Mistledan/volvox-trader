export interface MarketRow {
  symbol: string;
  last: number;
  change_pct_24h: number;
  high_24h: number;
  low_24h: number;
}

export interface LeaderRow {
  username: string;
  equity_usd: number;
  pnl_pct: number;
  autopilot?: boolean;
}

export interface SignalRow {
  username: string;
  action: string;
  symbol: string;
  confidence: number;
  size: number;
  reasoning: string;
  status: string;
  time: number;
}

export interface Me {
  id: number;
  username: string;
  account_id: number;
  initial_balance_usd: number;
  autopilot: boolean;
  leader_username: string | null;
  last_cycle_at: number | null;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  value_usd: number;
  unrealized_pnl_usd: number;
}

export interface Portfolio {
  equity_usd: number;
  cash_usd: number;
  initial_balance_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  realized_today_usd: number;
  daily_loss_halted: boolean;
  positions: Position[];
  prices: Record<string, number>;
  updated_at: string;
}

export interface Decision {
  action: string;
  symbol: string;
  confidence: number;
  size: number;
  reasoning: string;
  status: string;
  timestamp: number;
}

export interface TradeRec {
  time: number;
  side: string;
  symbol: string;
  quantity: number;
  price: number;
  value_usd: number;
  pnl_usd: number;
  reasoning: string;
}