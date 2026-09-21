# 🌸 Aspiz Flowers

> A complete e-commerce platform developed for **Aspiz Flowers**, providing a modern online shopping experience with product management, shopping cart functionality, order management, authentication, inventory management, and WhatsApp Business integration.

**🌐 Live Website:** [https://aspizflowers.com](https://aspizflowers.com)

**📌 Status:** `Completed`

---

## 📖 About The Project

**Aspiz Flowers** is a full-stack e-commerce website built for a real-world flower business.

The project was developed to provide customers with a simple and modern way to browse products, manage their shopping cart, and place orders online, while providing the business with the tools required to manage products, inventory, customers, and orders.

The platform combines a **Django backend**, **MySQL database**, **Tailwind CSS frontend**, and **WhatsApp Business Cloud API** integration into a complete production-ready web application.

---

## ✨ Features

### 🛍️ E-Commerce

- Product catalog
- Product categories
- Product detail pages
- Shopping cart
- Cart quantity management
- Customer accounts
- Authentication
- Order creation
- Order management
- Inventory management
- Automatic inventory updates
- Tiered / wholesale pricing

### 👤 User Management

- User registration
- User login / logout
- Customer accounts
- Protected user functionality
- Administrative access

### 📦 Order Management

- Database-backed orders
- Customer order information
- Ordered products and quantities
- Order totals
- Order status management
- Administrative order management

### 📱 WhatsApp Integration

The platform integrates with the **WhatsApp Business Cloud API** to connect the website's order workflow with the business's WhatsApp communication system.

### ⚙️ Administration

The administrative system allows the business to manage:

- Products
- Categories
- Inventory
- Pricing
- Orders
- Customers
- Store data

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python / Django |
| Frontend | HTML / Tailwind CSS / JavaScript |
| Database | MySQL |
| API | WhatsApp Business Cloud API |
| Containerization | Docker |
| Web Server | Nginx |
| Hosting | Linux VPS |
| Version Control | Git / GitHub |

---

## 🏗️ Project Structure

```text
aspiz-flowers-website/
├── website/
│   ├── aspiz_flowers/
│   ├── templates/
│   ├── static/
│   ├── media/
│   ├── manage.py
│   └── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── LICENSE
├── .gitignore
└── README.md
```

The project follows a modular Django architecture, keeping application logic, templates, static assets, configuration, and deployment-related files separated.

---

## 🚀 Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/Riddlerf8/aspiz-flowers-website.git
cd aspiz-flowers-website
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r website/requirements.txt
```

### 4. Configure the environment

Create the local environment file:

```bash
cp website/.env.example website/.env
```

Then configure the required values.

> ⚠️ Environment variables are required for local and production configuration. See `.env.example` for the required configuration. Sensitive credentials are not included in the repository.

### 5. Run migrations

```bash
cd website
python manage.py migrate
```

### 6. Create an administrator

```bash
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

The application will be available at:

```text
http://127.0.0.1:8000
```

---

## 🐳 Docker

Docker configuration is included in the project for containerized development and deployment.

Build and start the containers:

```bash
docker compose up --build
```

Run in detached mode:

```bash
docker compose up -d --build
```

Stop the containers:

```bash
docker compose down
```

---

## 🌍 Deployment

The website is deployed on a **Linux VPS** and served through **Nginx**.

Production architecture:

```text
Production VPS
     │
     ▼
   Nginx
     │
     ▼
   Docker
     │
     ▼
   Django
     │
     ├── MySQL
     └── WhatsApp Business Cloud API
```

The production environment is kept separate from development configuration, with sensitive credentials stored outside the repository.

---

## 🔄 Project Workflow

```text
Development
     │
     ▼
   Git
     │
     ▼
  GitHub
     │
     │ Automatic Deployment
     ▼
Production VPS
     │
     ▼
   Docker
     │
     ▼
   Django
     │
     ▼
   Nginx
     │
     ▼
aspizflowers.com
```

The repository is treated as the project's **living source of truth**, allowing future development and deployment changes to be tracked through Git.

---

## 👥 Authors & Team

| Role | Name | GitHub |
|---|---|---|
| 👑 Team Lead | **Sepehr Abolhasan** | [`Riddlerf8`](https://github.com/Riddlerf8) |
| 🛡️ Security Team | **Sepehr Abolhasan** | [`Riddlerf8`](https://github.com/Riddlerf8) |
| 💻 Developer Team | **Eileen Ramezani** | [`eileenrmz`](https://github.com/eileenrmz) |
| 🛠️ Support Team | **Hesam Zaretavakoli** | [`hesamzaretavakkoli84-hue`](https://github.com/hesamzaretavakkoli84-hue) |
| 📈 SEO Team | **Arad Arabi** | [`aradarabi2006-spec`](https://github.com/aradarabi2006-spec) |

---

## 📊 Project Information

| Information          | Details                              |
| -------------------- | ------------------------------------ |
| Project              | Aspiz Flowers                        |
| Type                 | E-Commerce Platform                  |
| Status               | Completed                            |
| Backend              | Django                               |
| Programming Language | Python                               |
| Frontend             | HTML / Tailwind CSS / JavaScript     |
| Database             | MySQL                                |
| API Integration      | WhatsApp Business Cloud API          |
| Containerization     | Docker                               |
| Web Server           | Nginx                                |
| Hosting              | Linux VPS                            |
| Source Control       | Git / GitHub                         |
| Live Website         | https://aspizflowers.com             |

---

## 🔮 Future Development

Although the current project is completed, the repository can continue to evolve with future maintenance and improvements.

Potential future updates include:

- UI/UX improvements
- Performance optimization
- Additional e-commerce functionality
- Improved order management
- Additional WhatsApp functionality
- Enhanced monitoring and logging
- Security improvements
---

## 🔒 Project Scope

**Aspiz Flowers is maintained as a separate real-world development project.**

This repository is **not part of my cybersecurity portfolio**.

Cybersecurity research, Web Security Academy labs, penetration-testing exercises, vulnerability research, and related write-ups are maintained separately.

This repository focuses exclusively on the development, deployment, and maintenance of the **Aspiz Flowers e-commerce platform**.

---

## 📄 License

This project is proprietary software.

Copyright © 2026 Sepehr Abolhasan — All Rights Reserved.

The source code, original project materials, and project-specific
implementations are owned by **Sepehr Abolhasan** and developed and
maintained under **Vindelor**.

Unauthorized copying, modification, redistribution, commercial use,
or creation of derivative works is prohibited.

See [`LICENSE`](LICENSE) for the complete terms.
---

## 🔗 Links   

🌐 **Live Website**  
https://aspizflowers.com

💻 **GitHub Repository**  
https://github.com/Vindelor/aspiz-flowers-website

---

> **Aspiz Flowers — Built for the real world. 🌸**
