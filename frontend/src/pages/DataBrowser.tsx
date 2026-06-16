import { Button, Result } from 'antd';
import { useNavigate } from 'react-router-dom';

export default function DataBrowser() {
  const navigate = useNavigate();
  return (
    <Result
      status="info"
      title="数据浏览功能已合并"
      subTitle="文档列表和 Chunk 查看功能已移至「文档中心」，请前往查看。"
      extra={
        <Button type="primary" onClick={() => navigate('/admin/documents')}>
          前往文档中心
        </Button>
      }
    />
  );
}
