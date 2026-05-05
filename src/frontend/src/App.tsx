import { useState } from 'react';
import Layout from './components/Layout';
import ChatBot from './components/ChatBot';
import DocumentList from './components/DocumentList';
import SearchPanel from './components/SearchPanel';

type View = 'chat' | 'documents' | 'search';

function App() {
  const [activeView, setActiveView] = useState<View>('chat');

  return (
    <Layout activeView={activeView} onViewChange={setActiveView}>
      {activeView === 'chat' && <ChatBot />}
      {activeView === 'documents' && <DocumentList />}
      {activeView === 'search' && <SearchPanel />}
    </Layout>
  );
}

export default App;
