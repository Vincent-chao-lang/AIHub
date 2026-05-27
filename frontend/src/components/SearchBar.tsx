import { useState, type FormEvent } from "react";

interface Props {
  onSearch: (query: string) => void;
}

export default function SearchBar({ onSearch }: Props) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="search-bar">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="搜索你的 AI 对话记忆... 例如：'RAG 架构'"
        className="search-input"
      />
      <button type="submit" className="search-btn">
        &#x1F50D;
      </button>
    </form>
  );
}
