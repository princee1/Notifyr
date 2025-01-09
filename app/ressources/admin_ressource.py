from typing import Any
from fastapi import Depends, Request, Response
from services.config_service import ConfigService
from utils.dependencies import get_admin_token, get_bearer_token, get_client_ip,APIFilterInject
from container import InjectInMethod,Get
from definition._ressource import Guard, Permission, Pipe, Ressource,HTTPMethod



admin_page= '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Panel - Auth Key Management</title>
  <style>
    /* General Styles */
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 0;
      display: flex;
      height: 100vh;
    }

    .admin-container {
      display: flex;
      width: 100%;
    }

    /* Sidebar */
    .sidebar {
      background-color: #2c3e50;
      color: #ecf0f1;
      width: 250px;
      padding: 20px;
      box-sizing: border-box;
    }

    .sidebar h2 {
      font-size: 1.5rem;
      margin-bottom: 20px;
    }

    .sidebar nav ul {
      list-style: none;
      padding: 0;
    }

    .sidebar nav ul li {
      margin-bottom: 10px;
    }

    .sidebar nav ul li a {
      color: #ecf0f1;
      text-decoration: none;
      font-size: 1rem;
      padding: 5px 10px;
      display: block;
      border-radius: 4px;
    }

    .sidebar nav ul li a.active, .sidebar nav ul li a:hover {
      background-color: #34495e;
    }

    /* Main Content */
    .main-content {
      flex: 1;
      padding: 20px;
      box-sizing: border-box;
    }

    header h1 {
      font-size: 2rem;
      margin-bottom: 20px;
    }

    .auth-key-actions {
      margin-bottom: 30px;
    }

    .auth-key-actions button {
      padding: 10px 20px;
      font-size: 1rem;
      color: #fff;
      background-color: #3498db;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }

    .auth-key-actions button:disabled {
      background-color: #95a5a6;
      cursor: not-allowed;
    }

    .key-display {
      margin-top: 20px;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .key-display label {
      font-size: 1rem;
    }

    .key-display input {
      flex: 1;
      padding: 10px;
      font-size: 1rem;
      border: 1px solid #bdc3c7;
      border-radius: 4px;
    }

    .key-list table {
      width: 100%;
      border-collapse: collapse;
    }

    .key-list table th, .key-list table td {
      border: 1px solid #ddd;
      padding: 10px;
      text-align: left;
    }

    .key-list table th {
      background-color: #f4f4f4;
    }

    .key-list table tr:nth-child(even) {
      background-color: #f9f9f9;
    }

    .key-list .revoke-btn {
      padding: 5px 10px;
      color: #fff;
      background-color: #e74c3c;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }

    .key-list .revoke-btn:disabled {
      background-color: #bdc3c7;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <div class="admin-container">
    <!-- Sidebar -->
    <aside class="sidebar">
      <h2>Admin Panel</h2>
      <nav>
        <ul>
          <li><a href="#">Dashboard</a></li>
          <li><a href="#">User Management</a></li>
          <li><a href="#" class="active">Auth Keys</a></li>
          <li><a href="#">Settings</a></li>
        </ul>
      </nav>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <header>
        <h1>Auth Key Management</h1>
      </header>

      <section class="auth-key-actions">
        <button id="generate-key-btn">Generate Auth Key</button>
        <div class="key-display">
          <label for="auth-key">Generated Key:</label>
          <input type="text" id="auth-key" readonly>
          <button id="download-key-btn" disabled>Download Key</button>
        </div>
      </section>

      <section class="key-list">
        <h2>Previously Generated Keys</h2>
        <table>
          <thead>
            <tr>
              <th>Key ID</th>
              <th>Created Date</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1234567890abcdef</td>
              <td>2025-01-08</td>
              <td>Active</td>
              <td><button class="revoke-btn">Revoke</button></td>
            </tr>
            <tr>
              <td>abcdef1234567890</td>
              <td>2024-12-25</td>
              <td>Revoked</td>
              <td><button class="revoke-btn" disabled>Revoke</button></td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>

  <script>
    document.getElementById('generate-key-btn').addEventListener('click', () => {
      const authKey = Math.random().toString(36).substring(2, 18); // Generate random key
      document.getElementById('auth-key').value = authKey;
      document.getElementById('download-key-btn').disabled = false;

      document.getElementById('download-key-btn').addEventListener('click', () => {
        const blob = new Blob([authKey], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'auth_key.txt';
        a.click();
        URL.revokeObjectURL(url);
      });
    });
  </script>
</body>
</html>

'''


ADMIN_PREFIX = 'admin'
ADMIN_STARTS_WITH = '_admin'

@APIFilterInject
def admin_guard(admin_:str):
    
    print('admin_guard')
    configService =  Get(ConfigService)
    return True,''


def htmlContent_pipe(*args,**kwargs):
    response: Response =kwargs['response']
    print('htmlContent_pipe')
    response.headers['Content-Type'] = 'text/html'
    kwargs['response']=response
    return args,kwargs



class AdminRessource(Ressource):

    @InjectInMethod
    def __init__(self,configService:ConfigService):
        super().__init__(ADMIN_PREFIX)
        self.configService = configService
    
    # @Permission()
    # @Guard(admin_guard)
    # @Pipe(htmlContent_pipe)
    # @Ressource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def _api_admin_page(self,request:Request, response:Response,token_= Depends(get_bearer_token), client_ip_=Depends(get_client_ip),admin_=Depends(get_admin_token)):
        
        return admin_page