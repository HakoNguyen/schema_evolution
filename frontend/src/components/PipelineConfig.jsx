import React, { useState, useEffect } from 'react';
import { Sliders, Server, Plus, Edit2, Trash2, X, Save, RefreshCw, Layers, Search } from 'lucide-react';
import { useToast } from './NotificationToast';

export default function PipelineConfig() {
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
            <Sliders style={{ color: 'var(--primary-color)' }} /> Quản lý cấu hình Web UI
          </h2>
          <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Đọc và ghi trực tiếp các file cấu hình YAML trong thư mục <code style={{ color: 'var(--primary-color)' }}>config/main.yaml</code> và <code style={{ color: 'var(--primary-color)' }}>config/pipelines/*.yaml</code>.
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
            Luồng pipelines ({pipelines.length})
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
            Hệ thống (main.yaml)
          </button>
        </div>
      </div>

      {loading ? (
        <div className="no-data">Đang tải cấu hình...</div>
      ) : activeSubTab === 'system' ? (
        /* TAB 1: SYSTEM CONFIG (main.yaml) */
        <div style={{ background: 'var(--card-bg)', padding: '24px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginTop: 0, marginBottom: '20px', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={18} style={{ color: 'var(--primary-color)' }} /> Cấu hình hệ thống gốc (config/main.yaml)
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', color: 'var(--text-dim)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Registry Directory
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
                Quét Baseline Định Kỳ (seconds)
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
                Kafka Bootstrap Servers (CDC Event Bus)
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
                Telegram Bot Token
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
                Telegram Chat ID
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
              <Save size={16} /> Lưu vào file config/main.yaml
            </button>
          </div>
        </div>
      ) : (
        /* TAB 2: PIPELINES MANAGER (TABLE VIEW) */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Toolbar */}
          <div style={{
            display: 'flex',
            justify: 'space-between',
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
                placeholder="Tìm kiếm pipeline..."
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
              <Plus size={16} /> Thêm pipeline mới
            </button>
          </div>

          {/* Table View */}
          <div className="schema-table-wrapper">
            <table className="schema-table">
              <thead>
                <tr>
                  <th>Tên pipeline / File config</th>
                  <th>Source database</th>
                  <th>Target warehouse</th>
                  <th>Bảng theo dõi</th>
                  <th style={{ textAlign: 'right' }}>Thao tác</th>
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
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--success-color)', background: 'var(--success-bg)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--success-border)', textTransform: 'uppercase' }}>
                        {pipe.source?.type}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {pipe.source?.config?.host}:{pipe.source?.config?.port} ({pipe.source?.config?.database})
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: pipe.target?.type && pipe.target?.type !== 'none' ? 'var(--warning-color)' : 'var(--primary-color)', background: pipe.target?.type && pipe.target?.type !== 'none' ? 'var(--warning-bg)' : 'var(--primary-bg)', padding: '3px 8px', borderRadius: '4px', border: pipe.target?.type && pipe.target?.type !== 'none' ? '1px solid var(--warning-border)' : '1px solid var(--primary-border)', textTransform: 'uppercase' }}>
                        {pipe.target?.type && pipe.target?.type !== 'none' ? pipe.target.type : `Self-Monitor (${pipe.source?.type})`}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {pipe.target?.type && pipe.target?.type !== 'none' ? `${pipe.target?.config?.host || 'localhost'}` : 'Chỉ theo dõi Nguồn'}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {pipe.tables?.map(t => (
                          <span key={t} style={{ background: 'var(--body-bg)', color: 'var(--primary-color)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-color)', fontSize: '0.75rem' }}>
                            {t}
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
                          <Edit2 size={12} /> Sửa
                        </button>
                        <button
                          onClick={() => handleDeletePipeline(pipe.name)}
                          style={{ padding: '4px 10px', fontSize: '0.8rem', background: 'var(--danger-bg)', color: 'var(--danger-color)', border: '1px solid var(--danger-border)', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Trash2 size={12} /> Xóa
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
          justify: 'center',
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
                {editingPipeline ? `Sửa Pipeline: ${editingPipeline.name}` : 'Tạo Pipeline Mới'}
              </h3>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSavePipeline}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Tên Pipeline</label>
                <input
                  type="text"
                  required
                  disabled={!!editingPipeline}
                  placeholder="Ví dụ: pg_to_clickhouse"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  style={{ width: '100%', padding: '10px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', outline: 'none' }}
                />
              </div>

              {/* Source DB Section */}
              <div style={{ background: 'var(--body-bg)', padding: '14px', borderRadius: '8px', marginBottom: '16px', border: '1px solid var(--border-color)' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: 'var(--success-color)', fontWeight: 700, textTransform: 'uppercase' }}>SOURCE DATABASE (DB NGUỒN)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Engine</label>
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
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Host</label>
                    <input
                      type="text"
                      value={formData.sourceHost}
                      onChange={e => setFormData({ ...formData, sourceHost: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Port</label>
                    <input
                      type="number"
                      value={formData.sourcePort}
                      onChange={e => setFormData({ ...formData, sourcePort: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Database Name</label>
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
                <h4 style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: 'var(--warning-color)', fontWeight: 700, textTransform: 'uppercase' }}>TARGET WAREHOUSE (DB ĐÍCH)</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Engine</label>
                    <select
                      value={formData.targetType}
                      onChange={e => setFormData({ ...formData, targetType: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    >
                      <option value="clickhouse">ClickHouse</option>
                      <option value="mysql">MySQL</option>
                      <option value="postgres">PostgreSQL</option>
                      <option value="none">Self-Monitor Only (Không đồng bộ)</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Host</label>
                    <input
                      type="text"
                      value={formData.targetHost}
                      onChange={e => setFormData({ ...formData, targetHost: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Port</label>
                    <input
                      type="number"
                      value={formData.targetPort}
                      onChange={e => setFormData({ ...formData, targetPort: e.target.value })}
                      style={{ width: '100%', padding: '8px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Database Name</label>
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
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase' }}>Danh Sách Bảng Theo Dõi (Phân cách bởi dấu phẩy)</label>
                <input
                  type="text"
                  placeholder="Ví dụ: users, customers, orders"
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
                  Hủy Bỏ
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ background: 'var(--success-color)', color: '#fff' }}
                >
                  {editingPipeline ? 'Lưu Thay Đổi (YAML)' : 'Tạo File config/pipelines/*.yaml'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
