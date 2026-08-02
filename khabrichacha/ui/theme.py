def get_custom_css() -> str:
    return """
<style>
    *, *::before, *::after {
        box-sizing: border-box;
    }

    html, body {
        background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #1e1b4b 100%);
        color: #f3f4f6;
        font-family: 'Inter', -apple-system, sans-serif;
        margin: 0;
        padding: 0;
        height: 100vh;
        width: 100vw;
        overflow: hidden !important;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #818cf8;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 0.3rem;
    }

    .panel {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        padding: 14px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }

    /* ----- Status Bar ----- */
    .status-bar {
        background: rgba(255, 255, 255, 0.03);
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
    }

    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 30px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .status-ready {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.4);
    }
    .status-running {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.4);
    }

    /* ----- Navigation ----- */
    .nav-btn {
        width: 100% !important;
        justify-content: flex-start !important;
        text-align: left !important;
        padding: 0.5rem 0.8rem !important;
        border-radius: 8px !important;
        background: transparent !important;
        color: #9ca3af !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        cursor: pointer;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
        border: 1px solid transparent !important;
        text-transform: none !important;
    }
    .nav-btn:hover {
        background: rgba(99, 102, 241, 0.08) !important;
        color: #c7d2fe !important;
        border: 1px solid rgba(99, 102, 241, 0.2) !important;
    }
    .nav-btn.active {
        background: rgba(99, 102, 241, 0.15) !important;
        color: #818cf8 !important;
        border: 1px solid rgba(99, 102, 241, 0.35) !important;
        font-weight: 600 !important;
    }

    .new-chat-btn {
        width: 100% !important;
        background: rgba(99, 102, 241, 0.05) !important;
        color: #a5b4fc !important;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
        border-radius: 10px !important;
        padding: 0.55rem 1rem !important;
        font-weight: 600 !important;
        box-shadow: none !important;
        text-transform: none !important;
        transition: all 0.2s ease !important;
    }
    .new-chat-btn:hover {
        background: rgba(99, 102, 241, 0.12) !important;
        border: 1px solid rgba(99, 102, 241, 0.5) !important;
        color: #e0e7ff !important;
    }

    .history-btn {
        width: 100% !important;
        justify-content: flex-start !important;
        text-align: left !important;
        font-size: 0.8rem !important;
        padding: 0.45rem 0.6rem !important;
        color: #9ca3af !important;
        border: none !important;
        background: transparent !important;
        text-transform: none !important;
        border-left: 2px solid transparent !important;
        border-radius: 0px !important;
        margin: 1px 0 !important;
        box-shadow: none !important;
    }
    .history-btn:hover {
        background: rgba(255, 255, 255, 0.03) !important;
        color: #f3f4f6 !important;
        border-left: 2px solid rgba(99, 102, 241, 0.4) !important;
    }

    /* ----- Provider Checkboxes ----- */
    .provider-cb .q-checkbox__label {
        font-size: 0.8rem !important;
    }

    /* ----- Control Buttons ----- */
    .control-btn {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
        border: none;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.4rem 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    }
    .control-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
    }
    .control-btn.secondary {
        background: rgba(255, 255, 255, 0.06);
        box-shadow: none;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .control-btn.secondary:hover {
        background: rgba(255, 255, 255, 0.1);
    }

    /* ----- Log View ----- */
    .log-view {
        background: rgba(0, 0, 0, 0.35);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: #a5b4fc;
    }

    .results-panel {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 12px;
        min-height: 100px;
        color: #e0e7ff;
        font-size: 0.85rem;
    }

    /* ----- Tabs Overrides ----- */
    .q-tab__label {
        font-size: 0.8rem !important;
        font-weight: 500;
    }
    .q-tab--active .q-tab__label {
        color: #818cf8 !important;
    }
    .q-tab--active .q-tab__icon {
        color: #818cf8 !important;
    }
    .q-tabs__arrow {
        color: #818cf8;
    }

    /* ----- Strategy Badges ----- */
    .strategy-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 30px;
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .strategy-fast { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(52,211,153,0.4); }
    .strategy-lookup { background: rgba(59,130,246,0.2); color: #60a5fa; border: 1px solid rgba(96,165,250,0.4); }
    .strategy-structured { background: rgba(168,85,247,0.2); color: #c084fc; border: 1px solid rgba(192,132,252,0.4); }
    .strategy-comparison { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(251,191,36,0.4); }
    .strategy-analysis { background: rgba(236,72,153,0.2); color: #f472b6; border: 1px solid rgba(244,114,182,0.4); }
    .strategy-research { background: rgba(99,102,241,0.2); color: #818cf8; border: 1px solid rgba(129,140,248,0.4); }
    .strategy-deep { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(248,113,113,0.4); }
    /* ----- Collapsible Sidebar Transition ----- */
    .sidebar-panel {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    .sidebar-panel.collapsed {
        width: 0px !important;
        min-width: 0px !important;
        padding-left: 0px !important;
        padding-right: 0px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
        opacity: 0;
        pointer-events: none;
    }

    /* Custom thin scrollbar */
    ::-webkit-scrollbar {
        width: 5px;
        height: 5px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(0, 0, 0, 0.2);
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(99, 102, 241, 0.3);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(99, 102, 241, 0.6);
    }
</style>
"""
