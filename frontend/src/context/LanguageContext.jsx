import React, { createContext, useContext, useState } from 'react';

export const translations = {
  en: {
    // Header & Navigation
    clusters: 'Clusters',
    monitored_tables: 'Monitored Tables',
    pipeline_topology: 'Pipeline Topology',
    live_cdc_stream: 'Live CDC Stream',
    pipeline_config: 'Pipeline & System Config',
    schema_editor: 'Schema Editor',
    back_to_list: '← Back to list',
    light_mode: '☀️ Light Mode',
    dark_mode: '🌙 Dark Mode',

    // Sidebar
    streaming: 'STREAMING',
    
    // Metrics & Badges
    table: 'TABLE',
    version: 'VERSION',
    status: 'STATUS',
    pending_approval: 'Pending Approval',
    healthy: 'Healthy',
    auto_synced: 'Auto Synced',
    paused: 'Paused',

    // Tables List
    total_tables: 'TOTAL MONITORED TABLES',
    pending_tables: 'PENDING / FROZEN',
    active_pipelines: 'ACTIVE CDC PIPELINES',
    sync_rate: 'SYNC SUCCESS RATE',
    search_tables_ph: 'Filter tables by name or pair...',
    pair: 'REGISTRY PAIR',
    table_name: 'TABLE NAME',
    pipeline: 'CDC PIPELINE',
    is_frozen: 'STATUS',
    action: 'ACTION',
    view_details: 'View Details',

    // Schema Editor
    schema_editor_title: 'Schema Editor',
    select_table: 'Select Table:',
    select_table_ph: '-- Select a table to edit schema --',
    deploy_schema: 'Deploy New Schema',
    no_table_selected: 'Please select a table from the dropdown above to start editing columns.',
    loading_schema: 'Loading column structure...',
    column_name: 'COLUMN NAME',
    data_type: 'DATA TYPE',
    primary_key: 'Primary Key',
    nullable: 'Nullable',
    add_column: 'Add New Column',

    // Live Stream
    live_stream_title: 'Live CDC Event Stream',
    live_stream_sub: 'Real-time DDL and CDC payload audit log stream from Redpanda Kafka Broker',
    streaming_active: 'Real-Time Streaming Active',
    pause_stream: 'Pause Stream',
    resume_stream: 'Resume Stream',
    listening_events: 'Listening for real-time CDC events...',
    listening_desc: 'Connected to Redpanda Broker topic. DDL/Schema changes from Source DB will automatically appear here.',

    // Pipeline Topology
    topology_title: 'Pipeline Topology Visualizer',
    topology_sub: 'Real-time CDC data flow topology between Source DBs and Target Warehouses',
    refresh: 'Refresh',
    select_pipeline: 'Select pipeline:',
    all_pipelines: 'All pipelines',
    node_source: 'Source DB',
    node_broker: 'CDC Broker',
    node_engine: 'Gatekeeper Engine',
    node_target: 'Target Warehouse',
    monitored_tables_count: 'Monitored Tables',

    // Pipeline Config
    config_title: 'Pipeline & System Configuration',
    config_sub: 'Read and write YAML configuration files directly in config/main.yaml and config/pipelines/*.yaml.',
    pipelines_tab: 'Pipeline Flows',
    system_tab: 'System (main.yaml)',
    search_pipelines_ph: 'Search pipelines...',
    add_new_pipeline: 'Add New Pipeline',
    save_system_config: 'Save to config/main.yaml',
    edit: 'Edit',
    delete: 'Delete',
    cancel: 'Cancel',
    save_changes: 'Save Changes (YAML)',
    create_pipeline_file: 'Create config/pipelines/*.yaml',

    // Table Details & Pending Approval
    schema_structure: 'Schema Structure',
    current_version: 'Current',
    version_history: 'Version History',
    primary_key_label: 'Primary Key:',
    foreign_keys_label: 'Foreign Keys:',
    breaking_alert_title: 'Breaking Changes Pending Approval Detected',
    detected_at: 'Detected at:',
    test_sandbox: 'Run Isolated Sandbox Test',
    testing_sandbox: 'Testing Sandbox...',
    sandbox_tested: 'Sandbox Test Passed (Safe)',
    approve_ddl: 'Approve & Execute DDL',
    reject: 'Reject',
    processing: 'Processing...'
  },
  vi: {
    // Header & Navigation
    clusters: 'Clusters',
    monitored_tables: 'Bảng Theo Dõi',
    pipeline_topology: 'Sơ Đồ Pipeline',
    live_cdc_stream: 'Luồng CDC Trực Tiếp',
    pipeline_config: 'Cấu Hình Hệ Thống',
    schema_editor: 'Trình Sửa Schema',
    back_to_list: '← Quay lại danh sách',
    light_mode: '☀️ Chế độ sáng',
    dark_mode: '🌙 Chế độ tối',

    // Sidebar
    streaming: 'STREAMING',

    // Metrics & Badges
    table: 'BẢNG',
    version: 'PHIÊN BẢN',
    status: 'TRẠNG THÁI',
    pending_approval: 'Chờ Phê Duyệt',
    healthy: 'Hoạt Động',
    auto_synced: 'Tự Động Đồng Bộ',
    paused: 'Tạm Dừng',

    // Tables List
    total_tables: 'TỔNG SỐ BẢNG THEO DÕI',
    pending_tables: 'BẢNG CHỜ PHÊ DUYỆT',
    active_pipelines: 'PIPELINE CDC HOẠT ĐỘNG',
    sync_rate: 'TỶ LỆ ĐỒNG BỘ THÀNH CÔNG',
    search_tables_ph: 'Tìm kiếm bảng dữ liệu hoặc pipeline...',
    pair: 'CẶP ĐỒNG BỘ',
    table_name: 'TÊN BẢNG',
    pipeline: 'PIPELINE CDC',
    is_frozen: 'TRẠNG THÁI',
    action: 'THAO TÁC',
    view_details: 'Xem Chi Tiết',

    // Schema Editor
    schema_editor_title: 'Trình Chỉnh Sửa Schema',
    select_table: 'Chọn bảng dữ liệu:',
    select_table_ph: '-- Chọn bảng cần chỉnh sửa --',
    deploy_schema: 'Triển Khai Schema Mới',
    no_table_selected: 'Vui lòng chọn một bảng từ menu ở trên để bắt đầu chỉnh sửa cấu trúc cột.',
    loading_schema: 'Đang tải cấu trúc cột...',
    column_name: 'TÊN CỘT',
    data_type: 'KIỂU DỮ LIỆU',
    primary_key: 'Primary Key',
    nullable: 'Nullable',
    add_column: 'Thêm Cột Mới',

    // Live Stream
    live_stream_title: 'Luồng Sự Kiện CDC Trực Tiếp',
    live_stream_sub: 'Luồng audit log trực tiếp bắt các sự kiện DDL / Payload CDC từ Redpanda Kafka Broker',
    streaming_active: 'Đang Streaming Thời Gian Thực',
    pause_stream: 'Tạm Dừng',
    resume_stream: 'Tiếp Tục Stream',
    listening_events: 'Đang lắng nghe sự kiện CDC thời gian thực...',
    listening_desc: 'Hệ thống đang kết nối tới Redpanda Broker topic. Sự kiện thay đổi DDL/Schema từ Database Nguồn sẽ tự động xuất hiện tại đây.',

    // Pipeline Topology
    topology_title: 'Sơ Đồ Luồng Pipeline Topology',
    topology_sub: 'Sơ đồ luồng dữ liệu thời gian thực giữa các Database và Data Warehouse',
    refresh: 'Làm Mới',
    select_pipeline: 'Chọn pipeline:',
    all_pipelines: 'Tất cả pipelines',
    node_source: 'DB Nguồn',
    node_broker: 'CDC Broker',
    node_engine: 'Gatekeeper Engine',
    node_target: 'Warehouse Đích',
    monitored_tables_count: 'Bảng theo dõi',

    // Pipeline Config
    config_title: 'Quản Lý Cấu Hình Web UI',
    config_sub: 'Đọc và ghi trực tiếp các file cấu hình YAML trong thư mục config/main.yaml và config/pipelines/*.yaml.',
    pipelines_tab: 'Luồng Pipelines',
    system_tab: 'Hệ Thống (main.yaml)',
    search_pipelines_ph: 'Tìm kiếm pipeline...',
    add_new_pipeline: 'Thêm Pipeline Mới',
    save_system_config: 'Lưu vào file config/main.yaml',
    edit: 'Sửa',
    delete: 'Xóa',
    cancel: 'Hủy Bỏ',
    save_changes: 'Lưu Thay Đổi (YAML)',
    create_pipeline_file: 'Tạo File config/pipelines/*.yaml',

    // Table Details & Pending Approval
    schema_structure: 'Cấu Trúc Schema',
    current_version: 'Hiện tại',
    version_history: 'Lịch Sử Phiên Bản',
    primary_key_label: 'Khóa Chính (Primary Key):',
    foreign_keys_label: 'Khóa Ngoại (Foreign Keys):',
    breaking_alert_title: 'Phát Hiện Thay Đổi Có Rủi Ro Gãy Cấu Trúc (Breaking Changes Pending Approval)',
    detected_at: 'Thời gian phát hiện:',
    test_sandbox: 'Chạy Thử Trên Sandbox Cách Ly',
    testing_sandbox: 'Đang Kiểm Thử Sandbox...',
    sandbox_tested: 'Đã Kiểm Thử Sandbox An Toàn',
    approve_ddl: 'Phê Duyệt & Thực Thi DDL',
    reject: 'Từ Chối',
    processing: 'Đang Xử Lý...'
  }
};

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState('en'); // Default to English for professional look!

  const toggleLanguage = () => {
    setLang(prev => prev === 'en' ? 'vi' : 'en');
  };

  const t = (key) => {
    return translations[lang]?.[key] || translations['en']?.[key] || key;
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
