import React from 'react';
import { Database, Network, Zap, LayoutTemplate, Sliders, GitBranch, Activity } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

export default function Sidebar({ activePage, setActivePage }) {
  const { t } = useLanguage();

  const menuItems = [
    { id: 'data_flow', label: t('data_flow'), icon: <Activity size={18} /> },
    { id: 'monitored_tables', label: t('monitored_tables'), icon: <Database size={18} /> },
    { id: 'pipeline_topology', label: t('pipeline_topology'), icon: <Network size={18} /> },
    { id: 'live_events', label: t('live_cdc_stream'), icon: <Zap size={18} /> },
    { id: 'pipeline_config', label: t('pipeline_config'), icon: <Sliders size={18} /> },
    { id: 'edit_schema', label: t('schema_editor'), icon: <LayoutTemplate size={18} /> },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2><span className="brand-mark"><GitBranch size={13} /></span>Schema Evolution</h2>
      </div>

      <div className="sidebar-section">
        <div className="section-title">{t('streaming')}</div>
        <div className="table-list">
          {menuItems.map(item => (
            <div
              key={item.id}
              className={`table-item ${activePage === item.id ? 'active' : ''}`}
              role="button"
              tabIndex={0}
              aria-current={activePage === item.id ? 'page' : undefined}
              onClick={() => setActivePage(item.id)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setActivePage(item.id))}
            >
              <div className="table-icon">
                {React.cloneElement(item.icon, { size: 16 })}
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
