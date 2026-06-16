import { Button, Result, Space } from 'antd';
import { useNavigate } from 'react-router-dom';

export default function IngestionManager() {
  const navigate = useNavigate();
  return (
    <Result
      status="info"
      title="Ingestion 管理已合并"
      subTitle="文件上传已在「文档中心」集成。"
      extra={
        <Button type="primary" onClick={() => navigate('/admin/documents')}>
          前往文档中心
        </Button>
      }
    />
  );
}
