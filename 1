import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, FileText, Film, Rocket, Search } from "lucide-react";

const API_BASE = "http://127.0.0.1:8000";

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default function AppGrowthDashboard() {
  const [campaigns, setCampaigns] = useState([]);
  const [ideas, setIdeas] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [script, setScript] = useState(null);
  const [videoPrompt, setVideoPrompt] = useState(null);
  const [asset, setAsset] = useState(null);
  const [published, setPublished] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      setError("");
      const [campaignRows, ideaRows] = await Promise.all([
        getJson("/campaigns"),
        getJson("/content-ideas"),
      ]);
      setCampaigns(campaignRows);
      setIdeas(ideaRows);
      if (ideaRows.length && !selectedIdea) {
        setSelectedIdea(ideaRows[0]);
      }
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  const filteredIdeas = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ideas;
    return ideas.filter((idea) =>
      [idea.title, idea.hook, idea.pillar, idea.angle, idea.status]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q))
    );
  }, [ideas, query]);

  const selectedCampaign = useMemo(() => {
    if (!selectedIdea) return null;
    return campaigns.find((c) => c.id === selectedIdea.campaign_id || c.id === Number(selectedIdea.campaign_id));
  }, [campaigns, selectedIdea]);

  async function runAction(fn) {
    try {
      setLoading(true);
      setError("");
      await fn();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  async function generateScript() {
    if (!selectedIdea) return;
    await runAction(async () => {
      const res = await postJson(`/generate/content-ideas/${selectedIdea.id}/script`);
      setScript(res);
    });
  }

  async function generateVideoPrompt() {
    if (!selectedIdea) return;
    await runAction(async () => {
      const res = await postJson(`/generate/content-ideas/${selectedIdea.id}/video-prompt`);
      setVideoPrompt(res);
    });
  }

  async function approveIdea() {
    if (!selectedIdea) return;
    await runAction(async () => {
      await fetch(`${API_BASE}/approvals/content-ideas/${selectedIdea.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "approved", feedback: "Approved in dashboard", approved_by: "yaw" }),
      });
    });
  }

  async function generateAsset() {
    if (!selectedIdea) return;
    await runAction(async () => {
      const res = await postJson(`/assets/content-ideas/${selectedIdea.id}/generate`);
      setAsset(res);
    });
  }

  async function publishInstagram() {
    if (!selectedIdea) return;
    await runAction(async () => {
      const res = await postJson(`/publish/content-ideas/${selectedIdea.id}/instagram`);
      setPublished(res);
    });
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">AppGrowth Dashboard</h1>
            <p className="text-muted-foreground">Plan, generate, approve, and publish growth content for your app.</p>
          </div>
          <div className="flex items-center gap-2 rounded-2xl border px-3 py-2 shadow-sm">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search content ideas"
              className="border-0 shadow-none focus-visible:ring-0"
            />
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard title="Campaigns" value={campaigns.length} icon={<Rocket className="h-5 w-5" />} />
          <MetricCard title="Content Ideas" value={ideas.length} icon={<FileText className="h-5 w-5" />} />
          <MetricCard title="Approved" value={ideas.filter((i) => i.status === "approved").length} icon={<CheckCircle2 className="h-5 w-5" />} />
          <MetricCard title="Assets" value={asset ? 1 : 0} icon={<Film className="h-5 w-5" />} />
        </div>

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle>Content Ideas</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {filteredIdeas.map((idea) => (
                <button
                  key={idea.id}
                  onClick={() => {
                    setSelectedIdea(idea);
                    setScript(null);
                    setVideoPrompt(null);
                    setAsset(null);
                    setPublished(null);
                  }}
                  className={`w-full rounded-2xl border p-4 text-left transition hover:shadow-sm ${selectedIdea?.id === idea.id ? "border-primary" : "border-border"}`}
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="font-medium">{idea.title}</span>
                    <Badge variant="secondary">{idea.status}</Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">{idea.hook}</div>
                  <div className="mt-2 text-xs text-muted-foreground">{idea.pillar}</div>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle>{selectedIdea ? selectedIdea.title : "Select a content idea"}</CardTitle>
            </CardHeader>
            <CardContent>
              {selectedIdea ? (
                <Tabs defaultValue="overview" className="space-y-4">
                  <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="script">Script</TabsTrigger>
                    <TabsTrigger value="video">Video Prompt</TabsTrigger>
                    <TabsTrigger value="publish">Publish</TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="space-y-4">
                    <InfoRow label="Campaign" value={selectedCampaign?.app_name || "—"} />
                    <InfoRow label="Audience" value={selectedCampaign?.audience || "—"} />
                    <InfoRow label="Tone" value={selectedCampaign?.tone || "—"} />
                    <InfoRow label="Hook" value={selectedIdea.hook} />
                    <InfoRow label="Angle" value={selectedIdea.angle} />
                    <div className="flex flex-wrap gap-2 pt-2">
                      <Button onClick={generateScript} disabled={loading}>Generate Script</Button>
                      <Button onClick={generateVideoPrompt} variant="secondary" disabled={loading}>Generate Video Prompt</Button>
                      <Button onClick={approveIdea} variant="outline" disabled={loading}>Approve</Button>
                      <Button onClick={generateAsset} variant="secondary" disabled={loading}>Generate Asset</Button>
                      <Button onClick={publishInstagram} variant="outline" disabled={loading}>Publish Instagram</Button>
                    </div>
                  </TabsContent>

                  <TabsContent value="script" className="space-y-4">
                    {script ? <TextBlock title="Hook" text={script.hook} /> : <EmptyState text="Generate a script to see it here." />}
                    {script ? <TextBlock title="Script" text={script.script_text} /> : null}
                    {script ? <TextBlock title="Caption" text={script.caption} /> : null}
                    {script ? <TextBlock title="Hashtags" text={script.hashtags} /> : null}
                  </TabsContent>

                  <TabsContent value="video" className="space-y-4">
                    {videoPrompt ? <TextBlock title="Prompt" text={videoPrompt.prompt_text} /> : <EmptyState text="Generate a video prompt to see it here." />}
                    {videoPrompt ? <TextBlock title="Shot List" text={videoPrompt.shot_list} /> : null}
                    {videoPrompt ? <TextBlock title="Visual Style" text={videoPrompt.visual_style} /> : null}
                    {videoPrompt ? <TextBlock title="Camera Notes" text={videoPrompt.camera_notes} /> : null}
                  </TabsContent>

                  <TabsContent value="publish" className="space-y-4">
                    {asset ? <TextBlock title="Generated Asset" text={asset.asset_url} /> : <EmptyState text="Generate an asset to prepare for publishing." />}
                    {published ? <TextBlock title="Published Post ID" text={published.platform_post_id} /> : null}
                    {published ? <TextBlock title="Caption Used" text={published.caption_used} /> : null}
                  </TabsContent>
                </Tabs>
              ) : (
                <div className="text-muted-foreground">Choose a content idea to get started.</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, icon }) {
  return (
    <Card className="rounded-2xl shadow-sm">
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <div className="text-sm text-muted-foreground">{title}</div>
          <div className="text-2xl font-semibold">{value}</div>
        </div>
        <div className="rounded-2xl border p-3">{icon}</div>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="rounded-2xl border p-4">
      <div className="mb-1 text-sm text-muted-foreground">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  );
}

function TextBlock({ title, text }) {
  return (
    <div className="rounded-2xl border p-4">
      <div className="mb-2 text-sm font-medium">{title}</div>
      <pre className="whitespace-pre-wrap break-words text-sm text-muted-foreground">{text}</pre>
    </div>
  );
}

function EmptyState({ text }) {
  return <div className="rounded-2xl border border-dashed p-8 text-sm text-muted-foreground">{text}</div>;
}

