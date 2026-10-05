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
    deploy_new_schema: 'Deploy New Schema',
    select_table_edit: 'Select table:',
    select_table_edit_ph: '-- Select table to edit --',

    // Live Stream
    live_stream_title: 'Live CDC Event Stream',
    live_stream_sub: 'Real-time DDL and CDC payload audit log stream from Redpanda Kafka Broker',
    streaming_active: 'Real-Time Streaming Active',
    pause_stream: 'Pause Stream',
    resume_stream: 'Resume Stream',
    listening_events: 'Listening for real-time CDC events...',
    listening_desc: 'Connected to Redpanda Broker topic. DDL/Schema changes from Source DB will automatically appear here.',
    requires_approval: 'Requires Approval',
    auto_synced_badge: 'Auto Synced',

    // Pipeline Topology
    topology_title: 'Pipeline Topology Visualizer',
    topology_sub: 'Real-time CDC data flow topology between Source DBs and Target Warehouses',
    refresh: 'Refresh',
    select_pipeline: 'Select pipeline:',
    all_pipelines: 'All pipelines',
    node_source: 'Source DB',
    node_broker: 'CDC Broker',
    node_scheduler: 'Polling Scheduler',
    event_driven_mode: 'Event-Driven (Kafka CDC)',
    polling_mode: 'Polling (Interval)',
    node_engine: 'Gatekeeper Engine',
    node_target: 'Target Warehouse',
    monitored_tables_count: 'Monitored Tables',

    // Pipeline Config
    config_title: 'Web UI Configuration Management',
    config_sub: 'Read and write YAML configuration files directly in config/main.yaml and config/pipelines/*.yaml.',
    pipelines_tab: 'Pipeline Flows',
    system_tab: 'System (main.yaml)',
    system_config_title: 'Core System Configuration (config/main.yaml)',
    registry_dir: 'Registry Directory',
    scan_interval: 'Periodic Baseline Scan (seconds)',
    kafka_bootstrap: 'Kafka Bootstrap Servers (CDC Event Bus)',
    telegram_bot_token: 'Telegram Bot Token',
    telegram_chat_id: 'Telegram Chat ID',
    save_to_main_yaml: 'Save to config/main.yaml',
    search_pipeline_ph: 'Search pipelines...',
    add_new_pipeline: 'Add New Pipeline',
    col_pipeline_name: 'PIPELINE NAME / CONFIG FILE',
    col_detection_mode: 'DETECTION MODE',
    col_source_db: 'SOURCE DATABASE',
    col_target_wh: 'TARGET WAREHOUSE',
    col_monitored_tables: 'MONITORED TABLES',
    col_actions: 'ACTIONS',
    event_driven_kafka: '⚡ Event-Driven (Kafka)',
    polling_scanner: '⏰ Polling Scanner',
    periodic_scan: 'Periodic Scan',
    self_monitor_only: 'Self-Monitor Only (Source only)',
    source_only: 'Source database only',
    edit_btn: 'Edit',
    delete_btn: 'Delete',
    edit_pipeline_modal_title: 'Edit Pipeline',
    create_pipeline_modal_title: 'Create New Pipeline',
    pipeline_name_label: 'Pipeline Name',
    detection_section_title: 'SCHEMA CHANGE DETECTION MECHANISM (DETECTION)',
    detection_mode_label: 'Detection Mode',
    kafka_cdc_topic_label: 'Kafka CDC Topic',
    source_db_section_title: 'SOURCE DATABASE',
    target_wh_section_title: 'TARGET WAREHOUSE',
    engine_label: 'Engine',
    host_label: 'Host',
    port_label: 'Port',
    database_name_label: 'Database Name',
    self_monitor_option: 'Self-Monitor Only (No Sync)',
    monitored_tables_input_label: 'Monitored Tables List (Comma separated)',
    cancel_btn: 'Cancel',
    save_changes_btn: 'Save Changes (YAML)',
    create_file_btn: 'Create config/pipelines/*.yaml',
    loading_config: 'Loading configuration...',
    confirm_delete_pipeline: 'Are you sure you want to delete pipeline configuration file',

    // Table Details & Pending Approval
    schema_structure: 'Schema Structure',
    current_version: 'Current version',
    version_history: 'Version History',
    col_column_name: 'COLUMN NAME',
    col_data_type: 'DATA TYPE',
    col_nullable: 'NULLABLE',
    col_default_val: 'DEFAULT VALUE',
    primary_key_label: 'Primary Key:',
    foreign_keys_label: 'Foreign Keys:',
    no_schema_data: 'No schema data found. Awaiting initial synchronization.',
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
    deploy_new_schema: 'Triển Khai Schema Mới',
    select_table_edit: 'Chọn bảng dữ liệu:',
    select_table_edit_ph: '-- Chọn bảng cần chỉnh sửa --',

    // Live Stream
    live_stream_title: 'Luồng Sự Kiện CDC Trực Tiếp',
    live_stream_sub: 'Luồng audit log trực tiếp bắt các sự kiện DDL / Payload CDC từ Redpanda Kafka Broker',
    streaming_active: 'Đang Streaming Thời Gian Thực',
    pause_stream: 'Tạm Dừng Stream',
    resume_stream: 'Tiếp Tục Stream',
    listening_events: 'Đang lắng nghe sự kiện CDC thời gian thực...',
    listening_desc: 'Hệ thống đang kết nối tới Redpanda Broker topic. Sự kiện thay đổi DDL/Schema từ Database Nguồn sẽ tự động xuất hiện tại đây.',
    requires_approval: 'Cần Phê Duyệt',
    auto_synced_badge: 'Tự Động Đồng Bộ',

    // Pipeline Topology
    topology_title: 'Sơ Đồ Luồng Pipeline Topology',
    topology_sub: 'Sơ đồ luồng dữ liệu thời gian thực giữa các Database và Data Warehouse',
    refresh: 'Làm Mới',
    select_pipeline: 'Chọn pipeline:',
    all_pipelines: 'Tất cả pipelines',
    node_source: 'DB Nguồn',
    node_broker: 'CDC Broker',
    node_scheduler: 'Bộ Quét Định Kỳ',
    event_driven_mode: 'Hướng Sự Kiện (Kafka CDC)',
    polling_mode: 'Quét Định Kỳ (Interval)',
    node_engine: 'Gatekeeper Engine',
    node_target: 'Warehouse Đích',
    monitored_tables_count: 'Bảng theo dõi',

    // Pipeline Config
    config_title: 'Quản Lý Cấu Hình Web UI',
    config_sub: 'Đọc và ghi trực tiếp các file cấu hình YAML trong thư mục config/main.yaml và config/pipelines/*.yaml.',
    pipelines_tab: 'Luồng Pipelines',
    system_tab: 'Hệ Thống (main.yaml)',
    system_config_title: 'Cấu hình hệ thống gốc (config/main.yaml)',
    registry_dir: 'Thư Mục Registry',
    scan_interval: 'Quét Baseline Định Kỳ (giây)',
    kafka_bootstrap: 'Kafka Bootstrap Servers (CDC Event Bus)',
    telegram_bot_token: 'Telegram Bot Token',
    telegram_chat_id: 'Telegram Chat ID',
    save_to_main_yaml: 'Lưu vào file config/main.yaml',
    search_pipeline_ph: 'Tìm kiếm pipeline...',
    add_new_pipeline: 'Thêm pipeline mới',
    col_pipeline_name: 'TÊN PIPELINE / FILE CONFIG',
    col_detection_mode: 'CƠ CHẾ THEO DÕI (DETECTION)',
    col_source_db: 'SOURCE DATABASE',
    col_target_wh: 'TARGET WAREHOUSE',
    col_monitored_tables: 'BẢNG THEO DÕI',
    col_actions: 'THAO TÁC',
    event_driven_kafka: '⚡ Event-Driven (Kafka)',
    polling_scanner: '⏰ Polling Scanner',
    periodic_scan: 'Quét định kỳ',
    self_monitor_only: 'Self-Monitor Only (Chỉ theo dõi Nguồn)',
    source_only: 'Chỉ theo dõi Nguồn',
    edit_btn: 'Sửa',
    delete_btn: 'Xóa',
    edit_pipeline_modal_title: 'Sửa Pipeline',
    create_pipeline_modal_title: 'Tạo Pipeline Mới',
    pipeline_name_label: 'Tên Pipeline',
    detection_section_title: 'CƠ CHẾ PHÁT HIỆN THAY ĐỔI SCHEMA (DETECTION)',
    detection_mode_label: 'Chế độ phát hiện (Mode)',
    kafka_cdc_topic_label: 'Kafka CDC Topic',
    source_db_section_title: 'SOURCE DATABASE (DB NGUỒN)',
    target_wh_section_title: 'TARGET WAREHOUSE (DB ĐÍCH)',
    engine_label: 'Loại Database Engine',
    host_label: 'Địa chỉ Host',
    port_label: 'Cổng Port',
    database_name_label: 'Tên Database',
    self_monitor_option: 'Self-Monitor Only (Không đồng bộ)',
    monitored_tables_input_label: 'Danh Sách Bảng Theo Dõi (Phân cách bởi dấu phẩy)',
    cancel_btn: 'Hủy Bỏ',
    save_changes_btn: 'Lưu Thay Đổi (YAML)',
    create_file_btn: 'Tạo File config/pipelines/*.yaml',
    loading_config: 'Đang tải cấu hình...',
    confirm_delete_pipeline: 'Bạn có chắc chắn muốn xóa file cấu hình',

    // Table Details & Pending Approval
    schema_structure: 'Cấu Trúc Schema',
    current_version: 'Phiên bản hiện tại',
    version_history: 'Lịch Sử Phiên Bản',
    col_column_name: 'CỘT',
    col_data_type: 'KIỂU DỮ LIỆU',
    col_nullable: 'NULLABLE',
    col_default_val: 'GIÁ TRỊ MẶC ĐỊNH',
    primary_key_label: 'Khóa Chính (Primary Key):',
    foreign_keys_label: 'Khóa Ngoại (Foreign Keys):',
    no_schema_data: 'Không tìm thấy dữ liệu schema. Đang chờ đồng bộ đầu tiên.',
    breaking_alert_title: 'Phát Hiện Thay Đổi Có Rủi Ro Gãy Cấu Trúc (Breaking Changes Pending Approval)',
    detected_at: 'Thời gian phát hiện:',
    test_sandbox: 'Chạy Thử Trên Sandbox cách ly',
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
