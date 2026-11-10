import React, { useState, useEffect } from 'react';
import { Sliders, Server, Plus, Edit2, Trash2, X, Save, RefreshCw, Layers, Search } from 'lucide-react';
import { useToast } from './NotificationToast';
import { useLanguage } from '../context/LanguageContext';

export default function PipelineConfig() {
  const { t } = useLanguage();
  const [pipelines, setPipelines] = useState([]);
  const [systemConfig, setSystemConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSubTab, setActiveSubTab] = useState('pipelines'); // 'pipelines' | 'system'
  const [searchTerm, setSearchTerm] = useState('');
  
  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [editingPipeline, setEditingPipeline] = useState(null);
  
  // Form State for Pipeline Create/Edit
  const [formData, setFormData] = useState({
    name: '',
    detectionMode: 'polling',
    kafkaTopic: '',
    sourceType: 'postgres',
    sourceHost: 'localhost',
    sourcePort: 5432,
    sourceDb: 'sample_db',
    targetType: 'clickhouse',
    targetHost: 'localhost',
    targetPort: 8123,
    targetDb: 'default',
    tables: ''
  });

  const { addToast } = useToast();

  const fetchConfigs = () => {
    setLoading(true);
    Promise.all([
      fetch('/api/config/pipelines').then(r => r.json()),
      fetch('/api/config/system').then(r => r.json())
    ])
    .then(([pipes, sys]) => {
      setPipelines(pipes);
      setSystemConfig(sys);
    })
    .catch(err => {
      console.error("Lỗi khi tải cấu hình:", err);
      addToast("Không thể tải thông tin cấu hình từ API", "error");
    })
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const openModal = (pipeline = null) => {
    if (pipeline) {
      setEditingPipeline(pipeline);
      setFormData({
        name: pipeline.name || '',
        detectionMode: pipeline.detection?.mode || 'polling',
        kafkaTopic: pipeline.detection?.kafka?.topic || pipeline.name || '',
        sourceType: pipeline.source?.type || 'postgres',
        sourceHost: pipeline.source?.config?.host || 'localhost',
        sourcePort: pipeline.source?.config?.port || 5432,
        sourceDb: pipeline.source?.config?.database || '',
        targetType: pipeline.target?.type || 'clickhouse',
        targetHost: pipeline.target?.config?.host || 'localhost',
        targetPort: pipeline.target?.config?.port || 8123,
        targetDb: pipeline.target?.config?.database || '',
        tables: (pipeline.tables || []).join(', ')
      });
    } else {
      setEditingPipeline(null);
      setFormData({
        name: '',
        detectionMode: 'polling',
        kafkaTopic: '',
        sourceType: 'postgres',
        sourceHost: 'localhost',
        sourcePort: 5432,
        sourceDb: 'sample_db',
        targetType: 'clickhouse',
        targetHost: 'localhost',
        targetPort: 8123,
        targetDb: 'default',
        tables: 'users, orders'
      });
    }
    setShowModal(true);
  };

  const handleSavePipeline = (e) => {
    e.preventDefault();
    const tableList = formData.tables.split(',').map(t => t.trim()).filter(Boolean);
    
    const payload = {
      name: formData.name,
      detection: {
        mode: formData.detectionMode
      },
      source: {
        type: formData.sourceType,
        config: {
          host: formData.sourceHost,
          port: Number(formData.sourcePort),
          database: formData.sourceDb
        }
      },
      tables: tableList
    };

    if (formData.detectionMode === 'event_driven') {
      payload.detection.kafka = {
        topic: formData.kafkaTopic.trim() || formData.name
      };
    }

    if (formData.targetType && formData.targetType !== 'none') {
      payload.target = {
        type: formData.targetType,
        config: {
          host: formData.targetHost,
          port: Number(formData.targetPort),
          database: formData.targetDb
        }
      };
    }

    const url = editingPipeline ? `/api/config/pipelines/${editingPipeline.name}` : '/api/config/pipelines';
    const method = editingPipeline ? 'PUT' : 'POST';

    fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(res => {
      if (!res.ok) throw new Error("Lỗi khi lưu pipeline");
      return res.json();
    })
    .then(data => {
      addToast(data.message || "Đã lưu cấu hình pipeline thành công!", "success");
      setShowModal(false);
      fetchConfigs();
    })
    .catch(err => {
      console.error(err);
      addToast(err.message, "error");
    });
  };

  const handleDeletePipeline = (name) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa file cấu hình config/pipelines/${name}.yaml?`)) return;

    fetch(`/api/config/pipelines/${name}`, { method: 'DELETE' })
      .then(res => {
        if (!res.ok) throw new Error("Không thể xóa file pipeline");
        return res.json();
      })
      .then(data => {
        addToast(data.message || `Đã xóa pipeline ${name}`, "info");
        fetchConfigs();
      })
      .catch(err => {
        console.error(err);
        addToast(err.message, "error");
      });
  };

  const handleSaveSystemConfig = () => {
    fetch('/api/config/system', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(systemConfig)
    })
    .then(res => {
      if (!res.ok) throw new Error("Không thể cập nhật system config");
      return res.json();
    })
    .then(data => {
      addToast(data.message || "Đã lưu main.yaml!", "success");
      fetchConfigs();
    })
    .catch(err => {
      console.error(err);
      addToast(err.message, "error");
    });
  };

  const filteredPipelines = pipelines.filter(p => 
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.source?.type || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.target?.type || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div style={{ padding: '4px 0', color: 'var(--text-main)' }}>
      {/* Header & Sub-Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sliders style={{ color: 'var(--primary-color)' }} /> {t('config_title')}
          </h2>
          <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {t('config_sub')}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', background: 'var(--card-bg)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setActiveSubTab('pipelines')}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeSubTab === 'pipelines' ? 'var(--primary-color)' : 'transparent',
              color: activeSubTab === 'pipelines' ? '#0b0f17' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem'
            }}
          >
            {t('pipelines_tab')} ({pipelines.length})
          </button>
          <button
            onClick={() => setActiveSubTab('system')}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeSubTab === 'system' ? 'var(--primary-color)' : 'transparent',
              color: activeSubTab === 'system' ? '#0b0f17' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.85rem'
            }}
          >
            {t('system_tab')}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="no-data">{t('loading_config')}</div>
      ) : activeSubTab === 'system' ? (
        /* TAB 1: SYSTEM CONFIG (main.yaml) */
        <div style={{ background: 'var(--card-bg)', padding: '24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginTop: 0, marginBottom: '20px', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} style={{ color: 'var(--primary-color)' }} /> {t('system_config_title')}
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                {t('registry_dir')}
              </label>
              <input
                type="text"
                value={systemConfig?.registry?.dir || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  registry: { ...systemConfig.registry, dir: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                {t('scan_interval')}
              </label>
              <input
                type="number"
                value={systemConfig?.scheduler?.interval_seconds || 60}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  scheduler: { ...systemConfig.scheduler, interval_seconds: Number(e.target.value) }
                })}
                style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
              />
            </div>

            <div style={{ gridColumn: 'span 2' }}>
              <label style={{ display: 'block', marginBottom: '6px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                {t('kafka_bootstrap')}
              </label>
              <input
                type="text"
                value={systemConfig?.kafka?.bootstrap_servers || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  kafka: { ...systemConfig.kafka, bootstrap_servers: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                {t('telegram_bot_token')}
              </label>
              <input
                type="text"
                value={systemConfig?.telegram?.bot_token || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  telegram: { ...systemConfig.telegram, bot_token: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                {t('telegram_chat_id')}
              </label>
              <input
                type="text"
                value={systemConfig?.telegram?.chat_id || ''}
                onChange={(e) => setSystemConfig({
                  ...systemConfig,
                  telegram: { ...systemConfig.telegram, chat_id: e.target.value }
                })}
                style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
              />
            </div>
          </div>

          <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={handleSaveSystemConfig}
              className="btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <Save size={16} /> {t('save_to_main_yaml')}
            </button>
          </div>
        </div>
      ) : (
        /* TAB 2: PIPELINES MANAGER (TABLE VIEW) */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Toolbar */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--card-bg)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            padding: '12px 16px',
            gap: '16px'
          }}>
            <div style={{ position: 'relative', flex: 1, maxWidth: '380px' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
              <input
                type="text"
                placeholder={t('search_pipeline_ph')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px 8px 36px',
                  background: 'var(--body-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  color: 'var(--text-main)',
                  fontSize: '0.875rem',
                  outline: 'none'
                }}
              />
            </div>

            <button
              onClick={() => openModal(null)}
              className="btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--success-color)', color: '#fff' }}
            >
              <Plus size={16} /> {t('add_new_pipeline')}
            </button>
          </div>

          {/* Table View */}
          <div className="schema-table-wrapper">
            <table className="schema-table">
              <thead>
                <tr>
                  <th>{t('col_pipeline_name')}</th>
                  <th>{t('col_detection_mode')}</th>
                  <th>{t('col_source_db')}</th>
                  <th>{t('col_target_wh')}</th>
                  <th>{t('col_monitored_tables')}</th>
                  <th style={{ textAlign: 'right' }}>{t('col_actions')}</th>
                </tr>
              </thead>

              <tbody>
                {filteredPipelines.map((pipe) => (
                  <tr key={pipe.name}>
                    <td>
                      <div>
                        <strong style={{ color: 'var(--primary-color)', fontSize: '0.9rem' }}>{pipe.name}</strong>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                          <code>{pipe._filename || `${pipe.name}.yaml`}</code>
                        </div>
                      </div>
                    </td>
                    <td>
                      {pipe.detection?.mode === 'event_driven' ? (
                        <div>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#f59e0b', background: '#f59e0b1f', padding: '3px 8px', borderRadius: '4px', border: '1px solid #f59e0b40', textTransform: 'uppercase' }}>
                            {t('event_driven_kafka')}
                          </span>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            Topic: <code>{pipe.detection?.kafka?.topic || pipe.name}</code>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#3b82f6', background: '#3b82f61f', padding: '3px 8px', borderRadius: '4px', border: '1px solid #3b82f640', textTransform: 'uppercase' }}>
                            {t('polling_scanner')}
                          </span>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {t('periodic_scan')}
                          </div>
                        </div>
                      )}
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--success-color)', background: 'var(--success-bg)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--success-border)', textTransform: 'uppercase' }}>
                        {pipe.source?.type}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {pipe.source?.config?.host}:{pipe.source?.config?.port} ({pipe.source?.config?.database})
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: pipe.target?.type && pipe.target?.type !== 'none' ? 'var(--warning-color)' : 'var(--primary-color)', background: pipe.target?.type && pipe.target?.type !== 'none' ? 'var(--warning-bg)' : 'var(--primary-bg)', padding: '3px 8px', borderRadius: '4px', border: pipe.target?.type && pipe.target?.type !== 'none' ? '1px solid var(--warning-border)' : '1px solid var(--primary-border)', textTransform: 'uppercase' }}>
                        {pipe.target?.type && pipe.target?.type !== 'none' ? pipe.target.type : `SELF-MONITOR (${pipe.source?.type?.toUpperCase()})`}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {pipe.target?.type && pipe.target?.type !== 'none' ? `${pipe.target?.config?.host || 'localhost'}` : t('source_only')}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {pipe.tables?.map(tItem => (
                          <span key={tItem} style={{ background: 'var(--body-bg)', color: 'var(--primary-color)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-color)', fontSize: '0.75rem' }}>
                            {tItem}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                        <button
                          onClick={() => openModal(pipe)}
                          className="btn-outline"
                          style={{ padding: '4px 10px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Edit2 size={12} /> {t('edit_btn')}
                        </button>
                        <button
                          onClick={() => handleDeletePipeline(pipe.name)}
                          style={{ padding: '4px 10px', fontSize: '0.8rem', background: 'var(--danger-bg)', color: 'var(--danger-color)', border: '1px solid var(--danger-border)', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Trash2 size={12} /> {t('delete_btn')}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL EDIT / CREATE PIPELINE */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.6)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 999
        }}>
          <div style={{
            background: 'var(--card-bg)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            width: '640px',
            maxWidth: '92%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px',
            color: 'var(--text-main)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--primary-color)' }}>
                {editingPipeline ? `${t('edit_pipeline_modal_title')}: ${editingPipeline.name}` : t('create_pipeline_modal_title')}
              </h3>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSavePipeline}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>{t('pipeline_name_label')}</label>
                <input
                  type="text"
                  required
                  disabled={!!editingPipeline}
                  placeholder="Ex: pg_to_clickhouse"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
                />
              </div>

              {/* Detection Section */}
              <div style={{ background: 'var(--body-bg)', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: '#f59e0b', fontWeight: 700, textTransform: 'uppercase' }}>{t('detection_section_title')}</h4>
                <div style={{ display: 'grid', gridTemplateColumns: formData.detectionMode === 'event_driven' ? '1fr 1fr' : '1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('detection_mode_label')}</label>
                    <select
                      value={formData.detectionMode}
                      onChange={e => setFormData({ ...formData, detectionMode: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    >
                      <option value="polling">{t('polling_scanner')}</option>
                      <option value="event_driven">{t('event_driven_kafka')}</option>
                    </select>
                  </div>
                  {formData.detectionMode === 'event_driven' && (
                    <div>
                      <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('kafka_cdc_topic_label')}</label>
                      <input
                        type="text"
                        placeholder={formData.name || 'pg_to_mysql'}
                        value={formData.kafkaTopic}
                        onChange={e => setFormData({ ...formData, kafkaTopic: e.target.value })}
                        style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Source DB Section */}
              <div style={{ background: 'var(--body-bg)', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: 'var(--success-color)', fontWeight: 700, textTransform: 'uppercase' }}>{t('source_db_section_title')}</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('engine_label')}</label>
                    <select
                      value={formData.sourceType}
                      onChange={e => setFormData({ ...formData, sourceType: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    >
                      <option value="postgres">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="mongodb">MongoDB</option>
                      <option value="clickhouse">ClickHouse</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('host_label')}</label>
                    <input
                      type="text"
                      value={formData.sourceHost}
                      onChange={e => setFormData({ ...formData, sourceHost: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('port_label')}</label>
                    <input
                      type="number"
                      value={formData.sourcePort}
                      onChange={e => setFormData({ ...formData, sourcePort: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('database_name_label')}</label>
                    <input
                      type="text"
                      value={formData.sourceDb}
                      onChange={e => setFormData({ ...formData, sourceDb: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                </div>
              </div>

              {/* Target DB Section */}
              <div style={{ background: 'var(--body-bg)', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: 'var(--warning-color)', fontWeight: 700, textTransform: 'uppercase' }}>{t('target_wh_section_title')}</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('engine_label')}</label>
                    <select
                      value={formData.targetType}
                      onChange={e => setFormData({ ...formData, targetType: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    >
                      <option value="clickhouse">ClickHouse</option>
                      <option value="mysql">MySQL</option>
                      <option value="postgres">PostgreSQL</option>
                      <option value="none">{t('self_monitor_option')}</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('host_label')}</label>
                    <input
                      type="text"
                      value={formData.targetHost}
                      onChange={e => setFormData({ ...formData, targetHost: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('port_label')}</label>
                    <input
                      type="number"
                      value={formData.targetPort}
                      onChange={e => setFormData({ ...formData, targetPort: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('database_name_label')}</label>
                    <input
                      type="text"
                      value={formData.targetDb}
                      onChange={e => setFormData({ ...formData, targetDb: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                </div>
              </div>

              {/* Tables Section */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>{t('monitored_tables_input_label')}</label>
                <input
                  type="text"
                  placeholder="Ex: users, customers, orders"
                  value={formData.tables}
                  onChange={e => setFormData({ ...formData, tables: e.target.value })}
                  style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn-outline"
                >
                  {t('cancel_btn')}
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ background: 'var(--success-color)', color: '#fff' }}
                >
                  {editingPipeline ? t('save_changes_btn') : t('create_file_btn')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
