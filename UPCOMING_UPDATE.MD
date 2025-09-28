# 🚀 Next Update & Feature Implementation Plan

This document outlines the upcoming tasks, considerations, and improvements to implement in the next update.  
It is organized by domain:

- ⚙️ Mini Service  
- 🐳 Deployment (Docker)  
- 📂 S3 File Management  
- 🔒 Security Policies  
- 💰 Cost Management  

---

## ⚙️ Mini Service

### 🔧 Service Management
- **Implement mini service and mini store logic**  
  - Create a dedicated **mini service layer**.  
  - Implement a **mini store** to persist mini service states.  
  - Add a **lock mechanism** when retrieving or updating data to ensure consistency.  

- **Service status locks**  
  - Maintain a lock status per service to decide if it is **usable or blocked**.  
  - Ensure service status reflects **DB states** (e.g., profile state).  
  - Build a **decorator** to validate service usability in resources.  
  - Optionally add **caching** for faster access.  

- **Dependency graph of services**  
  - Maintain a set of dependencies between services.  
  - Represent this as a **service dependency graph**.  
  - Allow each service to know which other services depend on it.  

### 🛠️ Decorator Improvements
- **Service dependency behavior**  
  - Enhance decorators to define **dependency levels** between services.  
  - Configure **reload behavior**:  
    - Should the service **rebuild**?  
    - At which stage?  
    - Or simply **ignore** and continue?  
  - Allow decorators to dynamically **change service status** based on dependencies.  

### 👤 Profile & Worker Integration
- **Profile data retrieval**  
  - Design a flexible way to **retrieve profile data**, adaptable to **Celery workers**.  

### 📦 Mini Store & Container
- **Mini store completion**  
  - Finalize the mini store logic.  
  - Create a **mini container** that:  
    - Links service management and deletion.  
    - Maintains references to mini services.  

- **Stream channel management**  
  - Enable **pause, resume, create, delete, and purge** operations on stream channels.  
  - Define whether these are managed as **mini services**.  
  - Ensure behavior is **delegated to the profile service**.  

### 🧩 Example Scenario
- If **HashiCorp Vault (HC Vault)** fails temporarily:  
  - **Secrets service** and **JWT service** should remain available.  
  - **Mongoose** and **Postgres** services may be marked as unavailable.  

---

## 🐳 Deployment (Docker)

### 🌐 Networking & Security
- **Monitoring subnet**  
  - Create a subnet for monitoring containers.  
  - Allow secure access via **tunnels**.  

- **DMZ (Demilitarized Zone)**  
  - Deploy the **landing page** inside a DMZ for security.  

- **Docker API integration**  
  - Implement a **Docker API** for container and resource management.  

- **Network setup**  
  - Complete the **Docker networks** design and configuration.  

- **Secrets & volumes security**  
  - Configure **Docker secrets** properly.  
  - Audit **cross-mounted volumes** for security compliance.  

### 🔄 Flexibility
- Ensure deployment allows for **server availability flexibility**.  

---

## 📂 S3 File Management

### 📁 Volume Strategy
- Each container must mount an **assets volume**.  
  - If no S3 is required → mount the **base assets directory**.  
  - If S3 is required → mount the **S3 container volume**.  

### 🖼️ Asset Management
- Provide a dedicated **asset manager image** with capabilities to:  
  - 📤 Upload  
  - 📥 Download  
  - 🗑️ Delete  
  - 📃 List  

### 🔔 Syncing & Notifications
- **Serverless integration**  
  - Implement a serverless function to **sync app database** with S3.  
  - The function will:  
    1. ✅ Validate **permissions** against the app.  
    2. 📦 Forward requests to **S3**.  
    3. 🔄 Send a **syncing notification** to update app memory.  

---

## 🔒 Security Policies

### 📜 Policy Management
- **Decouple JWT secrets from access policies**.  
- Store and manage **policies per client or group**.  
- Policies should cover:  
  - 👤 Profiles  
  - 📂 Assets  
  - 🌍 Routes  

### 🛡️ Policy Behavior
- On resource deletion → ensure related **policies are removed**.  
- Implement **policy decorators** for permission checks.  

### 🔐 Additional Security
- Limit the number of tokens a client can generate.  
- Lock middleware when **policies are being updated**.  
  - This could itself be managed as a **mini service**.  

---

## 💰 Cost Management

### ⏳ Rate Limiting
- Mount a **rate-limit JSON** configuration file.  

### 💸 Refund Mechanism
- Implement a **refund system** for specific requests (e.g., failed or unnecessary processing).  

---
