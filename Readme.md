# Game Changers 🎮🛡️

**Game Changers** is a Full-Stack MVP developed to enhance child safety and combat hate speech within gaming environments. By integrating real-time monitoring and in-game consequences, this project aims to transform gaming into a more positive and secure space for all players.

## 🚀 The Vision
The core objective of Game Changers is to address the misuse of gaming platforms for hate speech. Unlike traditional reporting systems that operate after the fact, this solution explores implementing **in-game consequences**. If toxic behavior or hate speech is detected, the system can dynamically affect the player’s experience—such as limiting platform features or temporarily adjusting character abilities—to discourage negative behavior in real-time.

## ✨ Key Features
* **Real-Time Detection:** Monitoring tools designed to identify hate speech and "platform hopping" (moving between moderated and unmoderated spaces).
* **Dynamic Consequences:** Technical framework for triggering in-game penalties based on behavioral data.
* **Full-Stack Architecture:** A robust MVP built with a modern tech stack to handle high-frequency gaming data.
* **Safety-First Design:** Focused on protecting vulnerable users and fostering a healthy community.

## 🛠️ Tech Stack
* **Backend:** Python
* **Database:** MongoDB
* **Frontend:** React (Client-side implementation)
* **Version Control:** Git

## 📂 Project Structure
* `/Frontend`: The frontend dashboard and user interface components.
* `/backend`: The backend logic, including detection algorithms and API endpoints.

## 🚦 Getting Started

### Prerequisites
* Node.js & npm
* Python 3.x
* MongoDB

### Installation
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/omerdor001/game-changers-repo.git](https://github.com/omerdor001/game-changers-repo.git)
    cd game-changers-repo
    ```

2.  **Setup Agent:**
    ```bash
    cd agent
    pip install -r requirements.txt
    python agent.py     
    ```

3.  **Setup Server:**
    ```bash
    ollama pull llama3
    cd server
    pip install -r requirements.txt
    uvicorn server:app --host 0.0.0.0 --port 8000
    ```

4.  **Setup Frontend:**
    ```bash
    cd client
    npm install
    npm run dev
    ```

## 📈 Impact
By automating the monitoring of "bridge" behaviors between platforms, this tool provides a scalable solution for major gaming companies to reduce moderation costs and significantly improve user retention through a safer environment.
