import React, { useEffect, useState, useRef } from 'react';

function App() {
    const [status, setStatus] = useState(null);
    const [connected, setConnected] = useState(false);
    const logContainerRef = useRef(null);

    useEffect(() => {
        const ws = new WebSocket(`ws://${window.location.host}/ws`);

        ws.onopen = () => {
            setConnected(true);
            console.log("WS Connected");
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setStatus(data);
            } catch (e) {
                console.error("Parse error", e);
            }
        };

        ws.onclose = () => {
            setConnected(false);
        };

        return () => {
            ws.close();
        };
    }, []);

    useEffect(() => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
    }, [status?.logs]);

    const handleStart = async () => {
        try {
            const res = await fetch('/api/start', { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (e) {
            alert("Network Error");
        }
    };

    const handleStop = async () => {
        try {
            await fetch('/api/stop', { method: 'POST' });
        } catch (e) {
            alert("Network Error");
        }
    };

    const isRunning = status?.running || false;

    return (
        <div className="container">
            <header className="header">
                <h1>GPU Miner Control</h1>
                <div className={`status-badge ${connected ? 'online' : 'offline'}`}>
                    {connected ? 'Backend Connected' : 'Backend Disconnected'}
                </div>
            </header>

            <div className="stats-grid">
                <div className="card">
                    <h3>Status</h3>
                    <div className={`value ${isRunning ? 'running' : 'stopped'}`}>
                        {isRunning ? 'MINING' : 'STOPPED'}
                    </div>
                    {status?.pid && <div className="sub">PID: {status.pid}</div>}
                    <div className="sub">Uptime: {status?.stats?.uptime || 0}s</div>
                </div>

                <div className="card">
                    <h3>Hashrate</h3>
                    <div className="value">{status?.stats?.hashrate || '0 MH/s'}</div>
                    <div className="sub">
                        Algo: <span className="highlight">{status?.stats?.algo || '---'}</span>
                    </div>
                </div>

                <div className="card">
                    <h3>Shares</h3>
                    <div className="value">
                        {status?.stats?.accepted || 0} <span className="sub-value">/ {status?.stats?.rejected || 0}</span>
                    </div>
                    <div className="sub">Accepted / Rejected</div>
                    <div className="sub">Pool: {status?.stats?.pool || '---'}</div>
                </div>
            </div>

            <div className="controls">
                <button
                    className="btn start"
                    onClick={handleStart}
                    disabled={isRunning || !connected}
                >
                    START MINER
                </button>
                <button
                    className="btn stop"
                    onClick={handleStop}
                    disabled={!isRunning || !connected}
                >
                    STOP MINER
                </button>
            </div>

            <div className="logs-panel">
                <h3>Miner Logs</h3>
                <div className="logs-window" ref={logContainerRef}>
                    {status?.logs?.map((line, i) => (
                        <div key={i} className="log-line">{line}</div>
                    )) || <div className="log-line">No logs yet...</div>}
                </div>
            </div>
        </div>
    );
}

export default App;
