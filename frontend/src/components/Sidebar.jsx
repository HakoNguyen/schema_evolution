import React from 'react';
import { Database, LayoutTemplate, Settings, ShieldAlert } from 'lucide-react';

export default function Sidebar({ activePage, setActivePage }) {
  const menuItems = [
    { id: 'monitored_tables', label: 'Task/Flow Monitor', icon: <Database size={18} /> },
    { id: 'edit_schema', label: 'Edit Schema (Low-Code)', icon: <LayoutTemplate size={18} /> },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Schema Evolution</h2>
      </div>

      <div className="sidebar-section">
        <div className="section-title">STREAMING</div>
        <div className="table-list">
          {menuItems.map(item => (
            <div
              key={item.id}
              className={`table-item ${activePage === item.id ? 'active' : ''}`}
              onClick={() => setActivePage(item.id)}
            >
              <div className="table-icon" style={{ opacity: activePage === item.id ? 1 : 0.7 }}>
                {item.icon}
              </div>
              <div className="table-info">
                <div className="table-name">{item.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
