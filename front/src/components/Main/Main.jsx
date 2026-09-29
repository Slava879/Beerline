import './Main.css'

const Main = ({ children }) => {
    return (
        <main className="main">
            <div className="container main__container">
                {children}
            </div>
        </main>
    )
}

export default Main