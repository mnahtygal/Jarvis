import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Mic,
  Camera,
  Cpu,
  Activity,
  Terminal,
  Shield,
  Wifi,
  Volume2,
  Power,
  Sparkles,
  Clock3,
  Settings,
  MessageSquare,
  Bot,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const initialLogs = [
  "System boot complete.",
  "Microphone detected: Samson Q2U",
  "Camera detected: Insta360 Link",
  "Voice engine ready.",
  "Awaiting command...",
];

const quickActions = [
  "Open camera",
  "Test microphone",
  "What time is it?",
  "System status",
  "Tell me a joke",
  "Shutdown mock core",
];

function GlowRing({ listening }: { listening: boolean }) {
  return (
    <div className="relative flex items-center justify-center h-72 w-72 mx-auto">
      <motion.div
        className="absolute inset-0 rounded-full bg-cyan-400/10 blur-3xl"
        animate={{ scale: listening ? [1, 1.15, 1] : [1, 1.04, 1] }}
        transition={{ repeat: Infinity, duration: listening ? 1.3 : 3, ease: "easeInOut" }}
      />

      <motion.div
        className="absolute h-72 w-72 rounded-full border border-cyan-300/30"
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 14, ease: "linear" }}
      />

      <motion.div
        className="absolute h-60 w-60 rounded-full border border-sky-400/30 border-dashed"
        animate={{ rotate: -360 }}
        transition={{ repeat: Infinity, duration: 18, ease: "linear" }}
      />

      <motion.div
        className="absolute h-44 w-44 rounded-full bg-gradient-to-br from-cyan-400 via-sky-500 to-blue-700 shadow-2xl shadow-cyan-500/30"
        animate={{
          scale: listening ? [1, 1.08, 1] : [1, 1.03, 1],
          boxShadow: listening
            ? [
                "0 0 30px rgba(34,211,238,0.35)",
                "0 0 70px rgba(34,211,238,0.65)",
                "0 0 30px rgba(34,211,238,0.35)",
              ]
            : [
                "0 0 24px rgba(34,211,238,0.18)",
                "0 0 40px rgba(34,211,238,0.28)",
                "0 0 24px rgba(34,211,238,0.18)",
              ],
        }}
        transition={{ repeat: Infinity, duration: listening ? 1.2 : 2.8, ease: "easeInOut" }}
      />

      <div className="relative z-10 flex flex-col items-center text-center">
        <Bot className="h-14 w-14 text-white drop-shadow" />
        <div className="mt-3 text-white text-2xl font-semibold tracking-[0.25em]">JARVIS</div>
        <div className="mt-1 text-cyan-100/80 text-xs uppercase tracking-[0.4em]">
          {listening ? "Listening" : "Standby"}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  title,
  value,
  sub,
}: {
  icon: React.ComponentType<any>;
  title: string;
  value: string;
  sub: string;
}) {
  return (
    <Card className="bg-white/5 border-white/10 backdrop-blur-xl rounded-2xl shadow-xl">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{title}</div>
            <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
            <div className="mt-1 text-sm text-slate-400">{sub}</div>
          </div>
          <div className="rounded-2xl bg-cyan-400/10 p-3 border border-cyan-300/20">
            <Icon className="h-5 w-5 text-cyan-300" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function JarvisGuiMockup() {
  const [listening, setListening] = useState(false);
  const [command, setCommand] = useState("");
  const [logs, setLogs] = useState(initialLogs);

  const currentTime = useMemo(() => {
    return new Date().toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  }, []);

  const submitCommand = () => {
    if (!command.trim()) return;
    setLogs((prev) => [`User: ${command}`, `Jarvis: Mock response for \"${command}\"`, ...prev]);
    setCommand("");
  };

  const triggerAction = (text: string) => {
    setLogs((prev) => [`Action: ${text}`, `Jarvis: Ready to simulate ${text.toLowerCase()}.`, ...prev]);
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.16),_transparent_25%),linear-gradient(180deg,_#020617_0%,_#06101f_45%,_#020617_100%)] text-white">
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6"
        >
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-cyan-300 text-sm uppercase tracking-[0.35em]">
                <Sparkles className="h-4 w-4" />
                Jetson Voice Console
              </div>
              <h1 className="mt-2 text-4xl md:text-5xl font-bold tracking-tight">Jarvis Command Center</h1>
              <p className="mt-2 text-slate-300 max-w-2xl">
                A cinematic mock interface for your Jetson-powered assistant: voice, camera, status panels, and command flow.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Badge className="bg-emerald-400/15 text-emerald-300 border border-emerald-300/20 hover:bg-emerald-400/15">
                Core Online
              </Badge>
              <Badge className="bg-cyan-400/15 text-cyan-300 border border-cyan-300/20 hover:bg-cyan-400/15">
                Mic Ready
              </Badge>
              <Badge className="bg-violet-400/15 text-violet-300 border border-violet-300/20 hover:bg-violet-400/15">
                Camera Ready
              </Badge>
              <Button variant="outline" className="border-white/15 bg-white/5 text-white hover:bg-white/10 rounded-2xl">
                <Settings className="mr-2 h-4 w-4" /> Settings
              </Button>
            </div>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div className="xl:col-span-3 space-y-6">
            <StatCard icon={Cpu} title="CPU / AI" value="31%" sub="Jetson running cool" />
            <StatCard icon={Mic} title="Audio Input" value="Samson Q2U" sub="USB microphone active" />
            <StatCard icon={Camera} title="Vision" value="Insta360 Link" sub="Tracking camera online" />
            <StatCard icon={Wifi} title="Network" value="Connected" sub="Local services reachable" />
          </div>

          <div className="xl:col-span-6">
            <Card className="relative overflow-hidden bg-white/5 border-white/10 backdrop-blur-xl rounded-[28px] shadow-2xl min-h-[640px]">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(34,211,238,0.10),_transparent_40%)]" />
              <CardContent className="relative p-6 md:p-8 h-full flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Primary Interface</div>
                    <div className="text-2xl font-semibold mt-1">Voice Core</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs uppercase tracking-[0.25em] text-slate-400">Local Time</div>
                    <div className="text-xl font-semibold flex items-center gap-2 justify-end">
                      <Clock3 className="h-4 w-4 text-cyan-300" /> {currentTime}
                    </div>
                  </div>
                </div>

                <div className="flex-1 flex items-center justify-center py-4">
                  <GlowRing listening={listening} />
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                  <Button
                    onClick={() => setListening((s) => !s)}
                    className="rounded-2xl h-12 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold"
                  >
                    <Mic className="mr-2 h-4 w-4" /> {listening ? "Stop" : "Listen"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => triggerAction("Open camera feed")}
                    className="rounded-2xl h-12 border-white/15 bg-white/5 text-white hover:bg-white/10"
                  >
                    <Camera className="mr-2 h-4 w-4" /> Vision
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => triggerAction("Run system diagnostics")}
                    className="rounded-2xl h-12 border-white/15 bg-white/5 text-white hover:bg-white/10"
                  >
                    <Activity className="mr-2 h-4 w-4" /> Diagnose
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => triggerAction("Power menu opened")}
                    className="rounded-2xl h-12 border-white/15 bg-white/5 text-white hover:bg-white/10"
                  >
                    <Power className="mr-2 h-4 w-4" /> Power
                  </Button>
                </div>

                <div className="flex gap-3">
                  <Input
                    value={command}
                    onChange={(e) => setCommand(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submitCommand()}
                    placeholder="Type a command for mock testing..."
                    className="h-12 rounded-2xl border-white/10 bg-black/20 text-white placeholder:text-slate-500"
                  />
                  <Button onClick={submitCommand} className="h-12 rounded-2xl bg-white text-slate-900 hover:bg-slate-200 px-6">
                    <MessageSquare className="mr-2 h-4 w-4" /> Send
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="xl:col-span-3 space-y-6">
            <Card className="bg-white/5 border-white/10 backdrop-blur-xl rounded-2xl shadow-xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Terminal className="h-5 w-5 text-cyan-300" /> Activity Log
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-[280px] overflow-auto pr-1">
                  {logs.map((log, i) => (
                    <div key={i} className="rounded-xl border border-white/8 bg-black/20 px-3 py-2 text-sm text-slate-200">
                      {log}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10 backdrop-blur-xl rounded-2xl shadow-xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Sparkles className="h-5 w-5 text-cyan-300" /> Quick Actions
                </CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-2">
                {quickActions.map((item) => (
                  <Button
                    key={item}
                    variant="outline"
                    onClick={() => triggerAction(item)}
                    className="justify-start rounded-xl border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                  >
                    {item}
                  </Button>
                ))}
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10 backdrop-blur-xl rounded-2xl shadow-xl">
              <CardContent className="p-5">
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-emerald-400/10 p-3 border border-emerald-300/20">
                    <Shield className="h-5 w-5 text-emerald-300" />
                  </div>
                  <div>
                    <div className="text-sm uppercase tracking-[0.2em] text-slate-400">Security</div>
                    <div className="text-lg font-semibold">Local-only Mode</div>
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-300 leading-6">
                  This mockup is designed to become your real Jarvis shell later: microphone capture, whisper output, camera feed, and skill routing can all plug into this layout.
                </p>
                <div className="mt-4 flex items-center gap-2 text-sm text-cyan-300">
                  <Volume2 className="h-4 w-4" /> Piper voice ready for integration
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
