import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Plus } from "lucide-react";

const HISTORY_KEY = "aiofai:conversations"; // [{id,title,updatedAt}]

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState([]);

  const currentCid = useMemo(() => {
    const sp = new URLSearchParams(location.search);
    return sp.get("cid") || null;
  }, [location.search]);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(HISTORY_KEY);
      setItems(raw ? JSON.parse(raw) : []);
    } catch { setItems([]); }
  }, []);

  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === HISTORY_KEY) {
        try { setItems(e.newValue ? JSON.parse(e.newValue) : []); } catch {}
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const writeItems = (next) => {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    setItems(next);
  };

  const createNewChat = () => {
    const id = Date.now().toString(36);
    const newItem = { id, title: "새 대화", updatedAt: Date.now() };
    const next = [newItem, ...items].slice(0, 100);
    writeItems(next);
    navigate(`/?cid=${id}`);
  };

  const openChat = (id) => navigate(`/?cid=${id}`);

  return (
    <div
      className="w-64 border-r p-4 h-full flex-shrink-0 transition-all duration-300"
      style={{
        background: "rgba(245, 242, 234, 0.4)",
        backdropFilter: "blur(20px)",
        borderRightColor: "rgba(139, 168, 138, 0.15)",
      }}
    >
      {/* 헤더: 최근항목 + 새 채팅 버튼 */}
      <div className="flex items-center justify-between mb-4">
        <h2
          className="text-lg font-semibold"
          style={{ color: "#2d3e2c", fontSize: "1.2rem", fontWeight: 600 }}
        >
          최근항목
        </h2>
        <button
          aria-label="새 채팅"
          onClick={createNewChat}
          className="p-2 rounded-lg transition-colors"
          style={{ color: "#2d3e2c" }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(93,124,91,0.08)")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
        >
          <Plus className="w-5 h-5" />
        </button>
      </div>

      {/* 히스토리 리스트 */}
      <div className="space-y-3">
        {items.length === 0 ? (
          <div className="text-xs" style={{ color: "rgba(45, 62, 44, 0.5)" }}>
            최근 항목이 없습니다.
          </div>
        ) : (
          items.map((it) => {
            const isActive = currentCid === it.id;
            return (
              <div
                key={it.id}
                className={`sidebar-item p-3 rounded-lg cursor-pointer transition-all duration-400 relative overflow-hidden ${
                  isActive ? "ring-2" : ""
                }`}
                onClick={() => openChat(it.id)}
                title={it.title || "제목 없음"}
                style={{
                  background: "rgba(255, 255, 255, 0.8)",
                  backdropFilter: "blur(10px)",
                  border: `1px solid ${isActive ? "#8ba88a" : "rgba(139, 168, 138, 0.2)"}`,
                  borderRadius: "16px",
                  boxShadow: isActive ? "0 12px 40px rgba(93, 124, 91, 0.12)" : "none",
                }}
              >
                <div
                  className="shine-effect absolute top-0 left-0 w-full h-full pointer-events-none"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent, rgba(139, 168, 138, 0.1), transparent)",
                    transform: "translateX(-100%)",
                    transition: "transform 0.6s ease",
                  }}
                />
                <div className="flex items-center justify-between">
                  <h3
                    className="font-medium text-sm mb-1 truncate transition-colors duration-300"
                    style={{ color: "#5d7c5b", fontSize: "0.95rem", fontWeight: 600, maxWidth: "80%" }}
                  >
                    {it.title || "제목 없음"}
                  </h3>
                  {isActive && (
                    <span
                      className="ml-2 inline-block w-2 h-2 rounded-full"
                      style={{ background: "#5d7c5b" }}
                    />
                  )}
                </div>
                <p
                  className="text-xs mt-1 transition-colors duration-300 truncate"
                  style={{ color: "rgba(45, 62, 44, 0.5)", fontSize: "0.8rem", lineHeight: 1.4 }}
                >
                  {new Date(it.updatedAt).toLocaleString()}
                </p>
              </div>
            );
          })
        )}
      </div>

      <style jsx>{`
        .sidebar-item:hover {
          background: rgba(255, 255, 255, 0.9) !important;
          border-color: #8ba88a !important;
          transform: translateY(-4px) scale(1.02);
          box-shadow: 0 12px 40px rgba(93, 124, 91, 0.15);
        }
        .sidebar-item:hover .shine-effect {
          transform: translateX(100%);
        }
        .sidebar-item:hover h3 {
          color: #5d7c5b !important;
        }
        .sidebar-item:hover p {
          color: rgba(45, 62, 44, 0.7) !important;
        }
      `}</style>
    </div>
  );
};

export default Sidebar;