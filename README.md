# 📡 Multi-Channel Message Relay & AI Customer Service Assistant  

This project is a powerful and flexible messaging relay system supporting OTPs and simple notifications through multiple communication channels, including **Email**, **SMS**, and **Voice Calls**. It is built to be **robust, reliable, and highly available**, leveraging advanced scheduling powered by **Redis** and offloading tasks to **FastAPI Background Tasks** or **Celery Workers**.  

### 🚀 Features  
- **Multi-Channel Messaging:** Seamlessly relay messages via Email, SMS, and Voice Calls.  
- **OTP Support:** Secure one-time password delivery for authentication workflows.  
- **Scheduling & Background Tasks:** Efficiently manage message scheduling using **Redis**, with offloading handled by **FastAPI Background Tasks** or **Celery Workers** to ensure high reliability.  
- **Advanced Design Pattern:** Utilizes a customized **Decorator Design Pattern** and **IoC Container** on top of **FastAPI Routers** for clean, maintainable, and reusable code.  
- **AI Customer Service Assistant:** Leverages **LLM (Large Language Models)**, **RAG (Retrieval-Augmented Generation)**, and **Knowledge Graphs** for intelligent customer interactions.  
- **Speech Capabilities:** Integrates **Speech-to-Text** and **Text-to-Speech** for voice-based customer support.  
- **Analytics & Logging:** Sends analytics and information through **Discord Webhooks** and has a comprehensive **logging setup** for monitoring and debugging.  
- **Data Retrieval:** Access historical and real-time data through a **Redis backend**.  
- **Secure Communication:**  
  - Uses **Custom Client JWT Tokens** and **Custom API Keys** for secure communication.  
  - **RBAC Permission System** and **Rate Limiter** to enhance security and reliability.  
  - **Blacklist JWT Tokens** and **Remote Token Issuance** via an **Admin Router** for better control and security.  
- **Live Chat Support:** Integrates a limited public **WebSocket Endpoint** to enable real-time live chat with users.  

### 🎯 Use Cases  
- Multi-factor authentication via OTPs.  
- Automated notifications and alerts.  
- AI-powered virtual customer assistant for enhanced support experiences.  
- Real-time customer interactions with live chat support.  

### 🛠️ Tech Stack  
- **FastAPI**: High-performance web framework for building APIs.  
- **Redis**: Efficient scheduling, caching, and data retrieval mechanism.  
- **Celery**: Distributed task queue for background processing.  
- **LLM, RAG, KG**: AI capabilities for intelligent responses and support automation.  
- **WebSocket**: Real-time communication for live chat functionality.  
- **Discord Webhooks**: Sending analytics and system information.  

### 🔐 Security & Reliability  
- **Custom JWT Tokens & API Keys** for secure communication.  
- **RBAC Permission System** to control access levels.  
- **Rate Limiter** to prevent abuse and ensure high availability.  
- **Blacklist Mechanism** to revoke compromised tokens.  
- **Admin Router** for remote token management and enhanced security.  

### 🔧 Installation & Setup  
```bash

```
### 📄 License
This project is licensed under the Apache License.
