"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/services/api";

export default function AssistantPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [answer, setAnswer] = useState<string>("");

  const ask = useMutation({
    mutationFn: () => api.aiMarket(symbol.toUpperCase()),
    onSuccess: (data) => {
      setAnswer(
        String(data.explanation || data.summary || JSON.stringify(data, null, 2))
      );
    },
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="font-display text-4xl">AI-ассистент</h1>
        <p className="text-mist mt-2">
          Спросите про контекст монеты. AI объясняет данные движков — не придумывает сделки.
        </p>
      </div>
      <div className="rounded-xl border border-line bg-panel/50 p-5 space-y-4">
        <label className="block text-sm">
          Символ
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="mt-2 w-full rounded-md border border-line bg-ink px-3 py-2"
            placeholder="BTCUSDT"
          />
        </label>
        <button
          type="button"
          onClick={() => ask.mutate()}
          disabled={ask.isPending}
          className="rounded-md bg-accent/90 px-4 py-2 text-ink font-medium hover:bg-accent disabled:opacity-50"
        >
          {ask.isPending ? "Анализ…" : "Почему эта монета интересна?"}
        </button>
        {ask.isError && (
          <p className="text-warn text-sm">Не удалось получить ответ AI. Проверьте API.</p>
        )}
        {answer && (
          <div className="rounded-lg border border-line/80 p-4 text-sm whitespace-pre-wrap leading-relaxed">
            {answer}
          </div>
        )}
      </div>
    </div>
  );
}
