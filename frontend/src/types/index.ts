export interface Message {
  id: string;
  platform: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  title?: string;
  tags?: string;
  summary?: string;
  timestamp: string;
}

export interface ConversationSummary {
  conversation_id: string;
  platform: string;
  title?: string;
  preview: string;
  tags?: string;
  summary?: string;
  message_count: number;
  latest_timestamp: string;
}

export interface TimelineGroup {
  date: string;
  conversations: ConversationSummary[];
}

export interface SearchResult {
  message: Message;
  score: number;
}

export interface Stats {
  total_messages: number;
  by_platform: Record<string, number>;
  vector_index_count?: number;
}

export interface RelatedConversation {
  conversation_id: string;
  title?: string;
  platform: string;
  score: number;
  message_count: number;
  latest_timestamp: string;
}

export interface ProjectGroup {
  name: string;
  keywords: string[];
  conversations: RelatedConversation[];
  total_messages: number;
}

export interface TraversalPath {
  conversation_id: string;
  title: string;
  platform: string;
  distance: number;
  score: number;
  path: string[];
}

export interface ContextResponse {
  query: string;
  context_text: string;
  key_points: string[];
  related: RelatedConversation[];
  graph_traversal: TraversalPath[];
}

export interface GraphNode {
  id: string;
  type: "conversation" | "tag";
  label: string;
  platform: string;
  message_count: number;
  weight: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: "tag_link" | "similar" | "vector_similar";
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const PLATFORM_LABELS: Record<string, string> = {
  chatgpt: "ChatGPT",
  claude: "Claude",
  gemini: "Gemini",
  kimi: "Kimi",
  deepseek: "DeepSeek",
};

export const PLATFORM_COLORS: Record<string, string> = {
  chatgpt: "#10a37f",
  claude: "#d97706",
  gemini: "#4285f4",
  kimi: "#6c5ce7",
  deepseek: "#0066cc",
};
