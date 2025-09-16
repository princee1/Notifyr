# 📍 Notifyr Roadmap  

This roadmap defines **short-term, mid-term, and long-term goals** for Notifyr, prioritized by importance and aligned on a rough timeline.  

---

## 🚨 Urgent (ASAP – 1–2 weeks)
.  
- 🔑 Implement **Vault secrets** in developpement and fix `secret-id` rotation.  
- 📨 Implement **EmailReader abstraction** (IMAP parsing, thread building).  
- 🧩 Finalize **base email events** (open, click, bounce, reply).  
- 🛠 Improve **Celery worker robustness**; add `will_track` kwargs.  
- 📊 Add **Prometheus metrics** and complete **load balancer / Kubernetes setup**.  
- 🐍 Create a **Gunicorn image** for production deployment.  

---

## 🎯 Short-Term Goals (1–2 months)  

### 📧 Email & Profiles  
- 🔄 Enable **profile rotation** and toggle sender strategies.  
- 🚫 Block profiles with OAuth errors; log errors in a dedicated document.  
- 🗂 Finish **profile resources**.  
- 🕵️ Add **spam detection** pipeline.  
- 🖼 Insert **tracking pixel** in HTML messages.  

### 📦 Deployment  
- 🌐 Create a **dedicated Docker network** (isolate services, keep LB public).  
- 📝 Clean up **Makefile** (avoid renaming issues with git push).  
- 🗂 Maintain **separate `docker-compose` files** (dev vs prod).  

---

## 🛠 Mid-Term Goals (3–6 months)  

### 👥 Contacts & Campaigns  
- 🔁 Implement **subscribe/unsubscribe workflows**.  
- 🌍 Add **unsubscribe page** with reason capture.  
- 📈 Support **UTM campaign tracking**.  
- 📬 Test **reply events** and message fetching.  
- 🧩 Inject `__contact` data (ID, name, phone) into templates.  
- 🛡 Validate templates against **XSS attacks** (e.g., MarkupSafe).  

### 🔐 Security & Config  
- 🧹 Refactor configuration handling (`config_service`, server values).  
- ⏱ Finalize **RateLimiterService** and secure data storage.  
- 🧽 Remove `InjectInMethod` for `task.py` to work better and isolates needed services.  
- Qdd secret message for secret delevery using wrapped response to decipher the message once, 

### ⚙️ Infrastructure & Sync  
- 📡 Add **pubsub channel** for profile variable updates.  
- 🗂 Implement **distributed locking service** (synchronized across all workers).  
- 🔄 Add endpoint to **notify workers to refresh memory/assets**.  
- 🗃 Store global variables in DB for selective recreation.  
- 📅 Improve scheduling:  
  - `SchedulerInterface` for tasks.  
  - SQLite job stores (per container, mounted volume).  
  - Support APScheduler alongside Celery.  
- ↩️ Fix **generation ID workflow** with rollback support.  

---

## 🚀 Long-Term Goals (6–12 months)  

### 🤖 Advanced Features  
- 🧠 Integrate **local LLMs** (BERT, LLaMA) + OpenAI Realtime API.  
- 📱 Multi-channel messaging: **SMS, WhatsApp, RCS**.  
- 🔔 Monitoring & alerts in **Discord/webhooks**.  
- 🗂 SDK with **OpenAPI** spec.  
- 🗄 Redis cache for **LLM responses**.  
- 📧 Advanced email stack (Postfix, Dovecot hosting, proxy rotation).  
- 🕵️ Deliverability improvements: verify emails, bounce detection, monitoring.  

### 📊 Analytics & Campaigns  
- 📉 Campaign dashboards: session conversion, unsubscribe tracking.  
- 📨 Add transactional headers in outgoing emails.  
- 📑 Campaign analytics with contact/campaign workflows.  
- 🌐 Landing page for campaign opt-in/out.  

### ⚡ Distributed System Improvements  
- 📢 Publish **service state via pubsub** for global sync.  
- 🧩 Deduplicate incoming events (e.g., multiple `OPENED`).  
- 🗂 Add **Memcached for rate limiting**, S3 storage for dev, ELK stack for logs.  
- 🐳 Maintain **separate Dockerfiles** for dev/prod.  
- ⚖️ Implement **Go-based load balancer**:  
  - Ping-pong availability checks.  
  - Random / round-robin / weighted routing.  
  - Per-account access control with auth-keys.  
  - Traffic logging with `X-Forwarded-For`.  
  - Delegate atomic tasks to healthy servers via committee algorithm.  

---

## 🗺 System Vision (Map)  

`🔐 Vault Secrets` → `📧 Email Profiles` → `🧩 MiniServices` (per profile channel)  
→ `💲 Cost Tracking` → `⚙ Workflow Logic (Celery)` → `📡 Profile Rotation`  
→ `📦 S3 Storage` → `📊 ELK Logging` → `🐳 Docker Deployment + Networks`  
→ `🤖 AI/LLM Services` → `📱 Business Logic (Email, SMS, Twilio)`  
→ `🔄 Refactoring + Scaling`.  

---

## 📢 Marketing Message  

> 💬 **Communication goes both ways. Join us!**  
> Whether you’re a great listener, a great speaker, or both — Notifyr connects you.  

---
