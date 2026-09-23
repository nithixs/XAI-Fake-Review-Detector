import { useEffect, useState } from 'react'
import { api, useResource } from './api'
import { Empty, Icon } from './components'
import { AnalyticsPage, Catalogue, ProductPage } from './ProductPages'
import { AccountPage, AdminPage, AuthPage, LabPage, MethodologyPage } from './WorkspacePages'
import './reviewguard.css'

const go = (path) => { window.location.hash = `/${path}` }
export default function App() {
  const [route, setRoute] = useState(() => window.location.hash.slice(2) || 'products')
  const [user, setUser] = useState(() => { try { return JSON.parse(sessionStorage.getItem('reviewguard_user') || 'null') } catch { return null } })
  const [menu, setMenu] = useState(false)
  const [toast, setToast] = useState('')
  const [returnTo, setReturnTo] = useState('products')
  const health = useResource('/health')
  useEffect(() => {
    const onHashChange = () => { setRoute(window.location.hash.slice(2) || 'products'); setMenu(false); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  useEffect(() => {
    if (sessionStorage.getItem('reviewguard_token')) api.get('/auth/me').then(({ data }) => { setUser(data); sessionStorage.setItem('reviewguard_user', JSON.stringify(data)) }).catch((error) => { if (error.response?.status === 401) { sessionStorage.removeItem('reviewguard_token'); sessionStorage.removeItem('reviewguard_user'); setUser(null) } })
  }, [])
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 7000); return () => clearTimeout(timer) }, [toast])
  const [page, id] = route.split('/')
  const activePage = page === 'product' ? 'products' : page
  const navigation = [['products', 'grid', 'Discover products'], ['analytics', 'chart', 'Product analytics'], ['lab', 'spark', 'AI review lab'], ['account', 'bag', 'My account']]
  function login() { setReturnTo(page === 'login' ? 'products' : route); go('login') }
  async function logout() { try { await api.post('/auth/logout') } catch { /* Local logout also works if the backend is offline. */ } finally { sessionStorage.removeItem('reviewguard_token'); sessionStorage.removeItem('reviewguard_user'); setUser(null); go('products'); setToast('You have been signed out.') } }
  let content
  if (page === 'products' || !page) content = <Catalogue/>
  else if (page === 'product' && /^\d+$/.test(id)) content = <ProductPage key={id} id={id} user={user} onLogin={login} notify={setToast}/>
  else if (page === 'analytics') content = <AnalyticsPage id={id}/>
  else if (page === 'lab') content = <LabPage/>
  else if (page === 'account') content = <AccountPage key={user?.id || 'guest'} user={user} onLogin={login}/>
  else if (page === 'admin') content = <AdminPage key={user?.id || 'guest'} user={user} onLogin={login} notify={setToast}/>
  else if (page === 'methodology') content = <MethodologyPage/>
  else if (page === 'login') content = <AuthPage demoMode={health.data?.demo_mode} onAuthenticated={(newUser) => { setUser(newUser); setToast(`Welcome, ${newUser.name.split(' ')[0]}!`); go(newUser.role === 'admin' && returnTo === 'products' ? 'admin' : returnTo) }}/>
  else content = <Empty title="This page is not available" text="Let’s find your way back to the collection."><a href="#/products" className="button primary">Explore products</a></Empty>
  const pageLabel = [...navigation, ['admin', '', 'Admin dashboard'], ['methodology', '', 'Our technology'], ['login', '', 'Welcome']].find(([key]) => key === activePage)?.[2] || 'ReviewGuard'
  return <div className="app-shell"><a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Skip to content</a>{menu && <button aria-label="Close navigation" className="nav-overlay" onClick={() => setMenu(false)}/>}<aside className={`sidebar ${menu ? 'open' : ''}`}><a className="brand" href="#/products"><span className="brand-symbol"><Icon name="shield" size={25}/></span><span>ReviewGuard<span className="brand-dot">.</span><small>PRODUCT INTELLIGENCE</small></span></a><div className="workspace-label">WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(([path, icon, label]) => <a href={`#/${path}`} key={path} className={activePage === path ? 'active' : ''} aria-current={activePage === path ? 'page' : undefined}><Icon name={icon}/><span>{label}</span>{path === 'lab' && <span className="nav-ai">AI</span>}</a>)}</nav><div className="workspace-label second-label">MANAGEMENT</div><nav aria-label="Management navigation"><a href="#/admin" className={page === 'admin' ? 'active' : ''}><Icon name="shield"/><span>Admin dashboard</span></a><a href="#/methodology" className={page === 'methodology' ? 'active' : ''}><Icon name="info"/><span>Our technology</span></a></nav><div className="sidebar-bottom"><div className="xai-note"><span><Icon name="spark" size={17}/> A little more clarity.</span><p>Understand the why behind every review.</p><a href="#/methodology">Powered by explainable AI <Icon name="arrow" size={13}/></a></div>{user ? <div className="sidebar-user"><span className="avatar">{user.name[0].toUpperCase()}</span><div><strong>{user.name}</strong><small>{user.role === 'admin' ? 'Administrator' : 'Customer'}</small></div><button className="icon-button" aria-label="Sign out" title="Sign out" onClick={logout}><Icon name="logout" size={18}/></button></div> : <button className="sidebar-signin" onClick={login}><span className="avatar"><Icon name="user" size={17}/></span><span>Sign in to your account</span><Icon name="arrow" size={16}/></button>}</div></aside><div className="main-shell"><header className="topbar"><div><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenu(true)}><Icon name="menu"/></button><span className="breadcrumb">Workspace <span>/</span> <strong>{pageLabel}</strong></span></div><div className="topbar-right"><span className="environment-badge"><span className="live-dot"/>{health.data?.demo_mode ? 'Demo workspace' : 'Review intelligence'}</span>{user ? <a className="topbar-account" href="#/account"><span className="avatar small-avatar">{user.name[0].toUpperCase()}</span><span>{user.name.split(' ')[0]}</span></a> : <button className="button secondary compact" onClick={login}>Sign in <Icon name="arrow" size={14}/></button>}</div></header><main id="main-content" className="main-content" tabIndex={-1}>{content}</main><footer className="footer"><span><Icon name="shield" size={14}/> ReviewGuard · Product Review Intelligence</span><span>Built with ML. Explained with XAI.</span></footer></div>{toast && <div className="toast" role="status"><Icon name="check" size={20}/><span>{toast}</span><button className="icon-button" aria-label="Dismiss notification" onClick={() => setToast('')}><Icon name="close" size={16}/></button></div>}</div>
}
