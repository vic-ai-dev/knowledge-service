import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import AppLayout from './components/AppLayout';
import Overview from './pages/Overview';
import DocumentCenter from './pages/DocumentCenter';
import DataBrowser from './pages/DataBrowser';
import IngestionManager from './pages/IngestionManager';
import EvaluationPanel from './pages/EvaluationPanel';
import AIAssistant from './pages/AIAssistant';

const theme = {
  token: {
    colorPrimary: '#7C3AED',
    colorBgLayout: '#FAF5FF',
    borderRadius: 6,
  },
};

export default function App() {
  return (
    <ConfigProvider theme={theme}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/overview" replace />} />
            <Route path="overview" element={<Overview />} />
            <Route path="admin/documents" element={<DocumentCenter />} />
            <Route path="documents" element={<DataBrowser />} />
            <Route path="ingestion" element={<IngestionManager />} />
            <Route path="evaluation" element={<EvaluationPanel />} />
            <Route path="query" element={<AIAssistant />} />
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
