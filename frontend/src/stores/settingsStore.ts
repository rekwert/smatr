import { create } from "zustand";

type Filters = {
  minScore: number;
  smc: boolean;
  pump: boolean;
  timeframe: string;
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
    minScore: 75,
    smc: true,
    pump: true,
    timeframe: "15",
  },
  tradingMode: "assisted",
  setFilters: (partial) =>
    set((state) => ({ filters: { ...state.filters, ...partial } })),
  setTradingMode: (mode) => set({ tradingMode: mode }),
}));
