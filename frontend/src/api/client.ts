import type { Message, TimelineGroup, SearchResult, Stats, RelatedConversation, ProjectGroup, ContextResponse, GraphData } from "../types";

const API_BASE = "http://127.0.0.1:8712";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  getTimeline(platform?: string): Promise<TimelineGroup[]> {
    const params = platform ? `?platform=${platform}` : "";
    return request(`/timeline${params}`);
  },

  getConversation(conversationId: string): Promise<Message[]> {
    return request(`/conversations/${conversationId}`);
  },

  search(query: string): Promise<SearchResult[]> {
    return request("/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },

  getStats(): Promise<Stats> {
    return request("/stats");
  },

  getRelatedConversations(conversationId: string): Promise<RelatedConversation[]> {
    return request(`/conversations/${conversationId}/related`);
  },

  getProjects(): Promise<ProjectGroup[]> {
    return request("/projects");
  },

  getContext(query: string): Promise<ContextResponse> {
    return request("/context", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },

  getGraph(): Promise<GraphData> {
    return request("/graph");
  },
};
