"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { Cog, Lightbulb, RefreshCcw } from "lucide-react";

type SpaState = {
  temps?: { current_f?: number | null; setpoint_f?: number | null; units?: string };
  heater?: { on?: boolean };
  pumps?: { id?: string; label?: string; state?: string; speed?: string }[];
  lights?: {
    on?: boolean;
    color_rgb?: number[] | null;
    inmix?: {
      available?: boolean;
      zones?: {
        key?: string;
        name?: string;
        on?: boolean;
        rgb?: number[] | null;
        brightness?: number | null;
      }[];
    } | null;
  };
  errors?: { code?: string; message?: string; severity?: string }[];
  capabilities?: {
    canSetTemp?: boolean;
    pumpsCount?: number;
    hasLights?: boolean;
    hasInMix?: boolean;
  };
  meta?: {
    lastUpdated?: number;
    connectionState?: string;
    lastError?: string | null;
    lastErrorAt?: number | null;
    lastContactAt?: number | null;
  };
};

const ENGINE_BASE_URL =
  process.env.NEXT_PUBLIC_ENGINE_BASE_URL || "http://localhost:8000";

const themeStyle: CSSProperties = {
  ["--page-bg" as string]: "#0b0f14",
  ["--panel" as string]: "rgba(13, 20, 28, 0.74)",
  ["--panel-strong" as string]: "rgba(17, 25, 36, 0.9)",
  ["--border" as string]: "rgba(148, 163, 184, 0.2)",
  ["--accent" as string]: "#55d6be",
  ["--accent-strong" as string]: "#1dd4bf",
  ["--warning" as string]: "#f59e0b",
  ["--danger" as string]: "#f43f5e",
  ["--ink" as string]: "#e2e8f0",
};

const formatTemp = (value?: number | null) =>
  value === null || value === undefined ? "--" : `${value.toFixed(1)}°F`;

const heatColor = (value?: number | null) => {
  if (value === null || value === undefined) return "#94a3b8";
  const minTemp = 70;
  const maxTemp = 104;
  const clamped = Math.min(Math.max(value, minTemp), maxTemp);
  const ratio = (clamped - minTemp) / (maxTemp - minTemp);
  const hue = 210 - ratio * 210;
  return `hsl(${hue}, 90%, 60%)`;
};

const formatTime = (value?: number | null) =>
  value ? new Date(value * 1000).toLocaleTimeString() : "—";

export default function HomePage() {
  const [state, setState] = useState<SpaState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [refreshSeed, setRefreshSeed] = useState(0);
  const [lightPending, setLightPending] = useState(false);
  const [pumpPending, setPumpPending] = useState<string | null>(null);
  const [setpointDraft, setSetpointDraft] = useState<number | null>(null);
  const [setpointPending, setSetpointPending] = useState(false);
  const [setpointDragging, setSetpointDragging] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    console.debug("[spa] ENGINE_BASE_URL", ENGINE_BASE_URL);

    const poll = async () => {
      const url = `${ENGINE_BASE_URL}/spa/state`;
      try {
        console.debug("[spa] fetch", url);
        const response = await fetch(url, {
          cache: "no-store",
        });
        if (!response.ok) {
          const body = await response.text().catch(() => "");
          console.debug("[spa] non-200 response", response.status, body);
          throw new Error(`HTTP ${response.status}`);
        }
        console.debug("[spa] response ok", response.status);
        const data = (await response.json()) as SpaState;
        if (!active) return;
        setState(data);
        setError(null);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (err) {
        if (!active) return;
        console.error("[spa] fetch failed", err);
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!active) return;
        timer = setTimeout(poll, 2000);
      }
    };

    poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [refreshSeed]);

  const connectionState = state?.meta?.connectionState ?? "DISCONNECTED";
  const currentTemp = state?.temps?.current_f ?? null;
  const tempColor = heatColor(currentTemp);
  const setpointColor = heatColor(setpointDraft ?? currentSetpoint);
  const statusTone = useMemo(() => {
    switch (connectionState) {
      case "CONNECTED":
        return "bg-emerald-400/15 text-emerald-200 border-emerald-400/30";
      case "CONNECTING":
        return "bg-amber-400/15 text-amber-200 border-amber-400/30";
      case "ERROR":
        return "bg-rose-400/15 text-rose-200 border-rose-400/30";
      default:
        return "bg-slate-500/15 text-slate-200 border-slate-400/30";
    }
  }, [connectionState]);

  const pumps = state?.pumps ?? [];
  const errors = state?.errors ?? [];
  const lightsOn = Boolean(state?.lights?.on);
  const heaterOn = Boolean(state?.heater?.on);
  const canToggleLights =
    Boolean(state?.capabilities?.hasLights) && connectionState === "CONNECTED";
  const lightRgb = state?.lights?.color_rgb ?? null;
  const lightColor =
    lightRgb && lightRgb.length === 3
      ? `rgb(${lightRgb[0]}, ${lightRgb[1]}, ${lightRgb[2]})`
      : null;
  const inmixAvailable = Boolean(state?.capabilities?.hasInMix);
  const inmixZones = state?.lights?.inmix?.zones ?? [];
  const maxSetpointF = state?.capabilities?.maxSetpointF ?? 104;
  const currentSetpoint = state?.temps?.setpoint_f ?? null;

  useEffect(() => {
    if (setpointDragging || setpointPending) return;
    if (currentSetpoint === null) return;
    setSetpointDraft(currentSetpoint);
  }, [currentSetpoint, setpointDragging, setpointPending]);

  const toggleLight = async () => {
    if (!canToggleLights || lightPending) return;
    setLightPending(true);
    try {
      const response = await fetch(`${ENGINE_BASE_URL}/spa/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "light.toggle",
          payload: { on: !lightsOn },
        }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      setRefreshSeed((value) => value + 1);
    } catch (err) {
      console.error("[spa] command failed", err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLightPending(false);
    }
  };

  const cyclePump = async (pumpId: string) => {
    if (pumpPending) return;
    setPumpPending(pumpId);
    try {
      const response = await fetch(`${ENGINE_BASE_URL}/spa/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "pump.cycle",
          payload: { id: pumpId },
        }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      setRefreshSeed((value) => value + 1);
    } catch (err) {
      console.error("[spa] pump command failed", err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPumpPending(null);
    }
  };

  const submitSetpoint = async (value: number) => {
    if (setpointPending) return;
    setSetpointPending(true);
    try {
      const response = await fetch(`${ENGINE_BASE_URL}/spa/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "temp.set",
          payload: { setpoint_f: value },
        }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      setRefreshSeed((prev) => prev + 1);
    } catch (err) {
      console.error("[spa] setpoint failed", err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSetpointPending(false);
    }
  };

  return (
    <main
      className="min-h-screen bg-[radial-gradient(circle_at_top,#0f172a_0%,#0b0f14_55%,#06070a_100%)] text-[color:var(--ink)]"
      style={themeStyle}
    >
      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-24 left-10 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl float-slow" />
        <div className="pointer-events-none absolute top-20 right-0 h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl float-fast" />
        <div className="pointer-events-none absolute bottom-0 left-1/3 h-80 w-80 rounded-full bg-sky-400/10 blur-3xl float-slow" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 pb-14 pt-12">
        <header
          className="flex flex-col gap-6 rounded-3xl border border-[color:var(--border)] bg-[color:var(--panel)] p-6 shadow-[0_20px_80px_rgba(15,23,42,0.55)] backdrop-blur fade-up md:flex-row md:items-center md:justify-between"
          style={{ animationDelay: "80ms" }}
        >
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-[0.35em] text-emerald-200/70">
              Lan spa engine
            </p>
            <h1 className="font-display text-4xl font-semibold text-slate-100 md:text-5xl">
              HydroPulse Control
            </h1>
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
              <span className={`rounded-full border px-3 py-1 ${statusTone}`}>
                {connectionState.toLowerCase()}
              </span>
              <span className="text-slate-400">
                Engine: {ENGINE_BASE_URL}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full border border-emerald-400/40 bg-emerald-400/10 px-5 py-2 text-sm font-semibold text-emerald-100 transition hover:border-emerald-300/70 hover:bg-emerald-400/20"
              onClick={() => setRefreshSeed((value) => value + 1)}
            >
              Refresh now
            </button>
            <button className="rounded-full border border-white/10 bg-white/5 px-5 py-2 text-sm text-slate-200 transition hover:bg-white/10">
              View logs (soon)
            </button>
          </div>
        </header>

        {error && (
          <div
            className="mt-6 rounded-2xl border border-rose-400/40 bg-rose-500/10 px-5 py-4 text-sm text-rose-100 fade-up"
            style={{ animationDelay: "140ms" }}
          >
            Failed to fetch: {error}
          </div>
        )}

        <section className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div
            className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel-strong)] p-5 shadow-lg fade-up"
            style={{ animationDelay: "180ms" }}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
                Temperature
              </span>
              <span className="text-xs text-emerald-200">
                Heater {heaterOn ? "On" : "Off"}
              </span>
            </div>
            <div className="mt-4 flex items-end gap-4">
              <div
                className="font-display text-5xl"
                style={{ color: tempColor }}
              >
                {formatTemp(currentTemp)}
              </div>
              <div className="text-sm text-slate-400">
                Target {formatTemp(state?.temps?.setpoint_f)}
              </div>
            </div>
            <div className="mt-5 h-2 rounded-full bg-white/5">
              <div
                className="h-2 rounded-full"
                style={{
                  width: currentTemp ? `${Math.min(currentTemp, 104)}%` : "0%",
                  backgroundColor: tempColor,
                }}
              />
            </div>
            <div className="mt-5 rounded-xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-400">
                <span>Setpoint</span>
                <span style={{ color: setpointColor }}>
                  {formatTemp(setpointDraft ?? currentSetpoint)}
                </span>
              </div>
              <input
                className="mt-3 w-full accent-emerald-300"
                type="range"
                min={80}
                max={maxSetpointF}
                step={0.5}
                value={setpointDraft ?? maxSetpointF}
                onChange={(event) =>
                  setSetpointDraft(Number(event.target.value))
                }
                onMouseDown={() => setSetpointDragging(true)}
                onTouchStart={() => setSetpointDragging(true)}
                onMouseUp={() => {
                  setSetpointDragging(false);
                  if (setpointDraft !== null) submitSetpoint(setpointDraft);
                }}
                onTouchEnd={() => {
                  setSetpointDragging(false);
                  if (setpointDraft !== null) submitSetpoint(setpointDraft);
                }}
                disabled={connectionState !== "CONNECTED" || !state?.capabilities?.canSetTemp}
              />
              <p className="mt-2 text-xs text-slate-400">
                Max {maxSetpointF}°F
                {setpointPending ? " · Sending..." : ""}
              </p>
            </div>
          </div>

          <div
            className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel-strong)] p-5 shadow-lg fade-up"
            style={{ animationDelay: "220ms" }}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                <Cog className="h-4 w-4 text-emerald-200/70" />
                Pumps
              </span>
              <span className="text-xs text-slate-400">
                {pumps.length} online
              </span>
            </div>
            <div className="mt-4 space-y-3">
              {pumps.length === 0 ? (
                <p className="text-sm text-slate-500">No pump data yet.</p>
              ) : (
                pumps.map((pump) => (
                  <div
                    key={pump.id ?? pump.label}
                    className="flex items-center justify-between rounded-xl border border-white/5 bg-white/5 px-3 py-2 text-sm"
                  >
                    <div>
                      <div className="font-medium text-slate-100">
                        {pump.label ?? "Pump"}
                      </div>
                      <div className="text-xs text-slate-400">
                        Mode {pump.speed ?? "—"}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-300">
                      <RefreshCcw
                        className={`h-4 w-4 ${
                          pump.state === "on"
                            ? String(pump.speed ?? "")
                                .toLowerCase()
                                .includes("lo")
                              ? "spin-reverse-slow text-emerald-200"
                              : "spin-reverse text-emerald-200"
                            : "text-slate-500"
                        }`}
                      />
                      <span className="uppercase tracking-[0.2em]">
                        {pump.state ?? "off"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="mt-4 space-y-2">
              {pumps.map((pump) => {
                const pumpKey = pump.id ?? pump.label ?? "Pump";
                return (
                  <button
                    key={`pump-action-${pumpKey}`}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-emerald-400/40 hover:bg-emerald-400/10 disabled:cursor-not-allowed disabled:text-slate-500"
                    disabled={
                      connectionState !== "CONNECTED" || pumpPending !== null
                    }
                    onClick={() => cyclePump(pumpKey)}
                  >
                    {pumpPending === pumpKey
                      ? "Sending..."
                      : `Cycle ${pump.label ?? pumpKey} mode`}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel-strong)] p-5 shadow-lg fade-up"
            style={{ animationDelay: "260ms" }}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                <Lightbulb className="h-4 w-4 text-emerald-200/70" />
                Lighting
              </span>
              <span className="text-xs text-slate-400">
                {state?.capabilities?.hasLights ? "Enabled" : "Unavailable"}
              </span>
            </div>
            <div className="mt-6 flex items-center justify-between">
              <div>
                <div className="font-display text-3xl text-slate-100">
                  {lightsOn ? "On" : "Off"}
                </div>
                <div className="text-xs text-slate-400">
                  Last updated {lastUpdated ?? "—"}
                </div>
              </div>
              <div
                className={`relative flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 transition ${
                  lightsOn ? "bg-emerald-400/15" : "bg-white/5"
                }`}
              >
                <div
                  className={`absolute h-16 w-16 rounded-2xl blur-2xl transition ${
                    lightsOn ? "bg-emerald-400/40" : "bg-transparent"
                  }`}
                />
                <Lightbulb
                  className={`relative h-9 w-9 ${
                    lightsOn ? "text-emerald-200" : "text-slate-400"
                  }`}
                />
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
              {inmixAvailable ? (
                <div className="flex items-center justify-between">
                  <span>Color control</span>
                  {lightColor ? (
                    <span className="flex items-center gap-2">
                      <span
                        className="h-3 w-3 rounded-full border border-white/20"
                        style={{ backgroundColor: lightColor }}
                      />
                      RGB {lightRgb?.join(", ")}
                    </span>
                  ) : (
                    <span>{inmixZones.length} zones</span>
                  )}
                </div>
              ) : (
                <span>Color control unavailable</span>
              )}
            </div>
            <button
              className="mt-4 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-emerald-400/40 hover:bg-emerald-400/10 disabled:cursor-not-allowed disabled:border-white/5 disabled:bg-white/5 disabled:text-slate-500"
              disabled={!canToggleLights || lightPending}
              onClick={toggleLight}
            >
              {lightPending
                ? "Sending..."
                : lightsOn
                  ? "Turn lights off"
                  : "Turn lights on"}
            </button>
          </div>

          <div
            className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel)] p-5 shadow-lg fade-up md:col-span-2"
            style={{ animationDelay: "300ms" }}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
                System health
              </span>
              <span className="text-xs text-slate-400">
                Last contact {formatTime(state?.meta?.lastContactAt)}
              </span>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Connection</p>
                <p className="text-lg text-slate-100">{connectionState}</p>
              </div>
              <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Last error</p>
                <p className="text-lg text-slate-100 truncate" title={state?.meta?.lastError ?? "None"}>
                  {state?.meta?.lastError ?? "None"}
                </p>
              </div>
              <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Last updated</p>
                <p className="text-lg text-slate-100">
                  {formatTime(state?.meta?.lastUpdated)}
                </p>
              </div>
              <div className="rounded-xl border border-white/5 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Capabilities</p>
                <p className="text-lg text-slate-100">
                  {state?.capabilities?.pumpsCount ?? 0} pumps,{" "}
                  {state?.capabilities?.canSetTemp ? "temp control" : "read-only"}
                </p>
              </div>
            </div>
          </div>

          <div
            className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel)] p-5 shadow-lg fade-up"
            style={{ animationDelay: "340ms" }}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
                Alerts
              </span>
              <span className="text-xs text-slate-400">
                {errors.length} active
              </span>
            </div>
            <div className="mt-4 space-y-3 text-sm">
              {errors.length === 0 ? (
                <p className="text-slate-400">No active alerts.</p>
              ) : (
                errors.map((entry, index) => (
                  <div
                    key={`${entry.code ?? "err"}-${index}`}
                    className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-rose-100"
                  >
                    <div className="font-medium">
                      {entry.code ?? "Alert"}
                    </div>
                    <div className="text-xs text-rose-200/80">
                      {entry.message ?? "Check spa console"}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        <section
          className="mt-8 rounded-2xl border border-[color:var(--border)] bg-[color:var(--panel)] p-5 fade-up"
          style={{ animationDelay: "380ms" }}
        >
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-display text-2xl text-slate-100">
                Raw state feed
              </h2>
              <p className="text-sm text-slate-400">
                Live snapshot from <code>/spa/state</code>
              </p>
            </div>
            <span className="text-xs text-slate-500">
              Updated {lastUpdated ?? "—"}
            </span>
          </div>
          <pre className="mt-4 max-h-72 overflow-auto rounded-xl border border-white/5 bg-black/30 p-4 text-xs text-slate-200">
            {state ? JSON.stringify(state, null, 2) : "Waiting for data..."}
          </pre>
        </section>
      </div>
    </main>
  );
}
