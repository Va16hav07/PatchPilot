import { NavLink } from 'react-router-dom'
import Icon, { type IconName } from './Icon'

function Tab({ to, icon, label }: { to: string; icon: IconName; label: string }) {
  return (
    <NavLink to={to} end className={({ isActive }) => `tab${isActive ? ' active' : ''}`}>
      <Icon name={icon} />
      {label}
    </NavLink>
  )
}

export default function TabBar() {
  return (
    <nav className="tabbar" aria-label="Main">
      <Tab to="/" icon="home" label="Today" />
      <Tab to="/insights" icon="chart" label="Insights" />
      <NavLink to="/log" className="tab-add" aria-label="Log a meal">
        <Icon name="plus" size={26} stroke={2.2} />
      </NavLink>
      <Tab to="/log" icon="search" label="Foods" />
      <Tab to="/profile" icon="user" label="Profile" />
    </nav>
  )
}
