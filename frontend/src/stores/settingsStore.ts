import { create } from "zustand";

export type FeedMode = "inefficiency" | "all" | "volume_scan";

type Filters = {
  minScore: number;
  smc: boolean;
  pump: boolean;
  timeframe: string;
  feed: FeedMode;
};

type TradingMode = "scanner" | "assisted" | "auto";

type Store = {
  filters: Filters;
  tradingMode: TradingMode;
  setFilters: (partial: Partial<Filters>) => void;
  setTradingMode: (mode: TradingMode) => void;
};

export const useSettingsStore = create<Store>((set) => ({
  filters: {
    minScore: 0,
    smc: true,
    pump: false,
    timeframe: "15",
    feed: "inefficiency",
  },
  tradingMode: "assisted",
  setFilters: (partial) =>
    set((state) => ({ filters: { ...state.filters, ...partial } })),
  setTradingMode: (mode) => set({ tradingMode: mode }),
}));
