def get_custom_css() -> str:
    return """
<style>
    body {
        background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #1e1b4b 100%);
        color: #f3f4f6;
        font-family: 'Inter', -apple-system, sans-serif;
        margin: 0;
        padding: 0;
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
        width: 100%;
        text-align: left;
        padding: 0.5rem 0.8rem;
        border-radius: 8px;
        border: none;
        background: transparent;
        color: #d1d5db;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .nav-btn:hover {
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
    }
    .nav-btn.active {
        background: rgba(99, 102, 241, 0.2);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.3);
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
</style>
"""
