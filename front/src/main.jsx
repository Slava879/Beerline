import { createRoot } from "react-dom/client"
import App from "./App"
import './styles/index.css'
import './styles/effects.scss'
import './styles/vars.css'
import './styles/blocks/vars-beeline.css'
import './styles/blocks/menu.css'
import './styles/blocks/menu-engineer.css'
import './styles/blocks/profile-engineer.css'
import './styles/blocks/choice-district.css'
import './styles/blocks/assign-master.css'
import './styles/blocks/urgent.css'
import './styles/blocks/incoming.css'
import './styles/blocks/engmenu.css'
import './styles/blocks/hover.css'
import './styles/responsive.css' 

createRoot(document.getElementById('root')).render(<App />)