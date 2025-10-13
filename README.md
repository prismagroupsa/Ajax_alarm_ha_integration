# 🛡️ Ajax Alarm System Integration for Home Assistant

Integrate your **Ajax Security System** seamlessly with **Home Assistant** — control, automate, and monitor your alarm system directly from your smart home dashboard.

---

## ⚠️ Secure Your Home Assistant Installation First!

Before installing this integration, **please make sure your Home Assistant instance is properly secured**.  
Following best practices will protect both your home network and your Ajax account.

### 🧱 Security Best Practices

- 🔑 Use a **strong and unique username and password**.  
- 🔒 Enable **Two-Factor Authentication (2FA)** for your Home Assistant account.  
- 🚫 **Do not expose** Home Assistant directly to the internet using the default port.  
  Instead, consider one (or combine several) of the following:
  - 🌀 **Reverse Proxy** (e.g., Nginx, Traefik)
  - ☁️ **Web Application Firewall (WAF)** such as [Cloudflare](https://www.cloudflare.com/)
  - 🔐 **Private VPN** access only

### 👤 Dedicated Account for Ajax
- Avoid using your **admin** account for this integration.  
- Create a **dedicated Ajax account** with **minimal permissions** (usually only ability to arm night mode is enough).  
- Configure **network access restrictions** — only allow connections from trusted networks.

---

## 🧩 Requirements

- Home Assistant **2024.6+**
- HACS installed
- Ajax account with limited permissions
- Internet access for Ajax API connectivity

---

## ⚠️ Supported Products

Actually we are supporting following products:
- Hub 2 (4G)
- Door Protect / Door Protect Plus
- Motion Protect
- Fire Protect Plus

This integration is actively maintained, and new device support will be introduced in future updates.

## ⚙️ Installation Guide

> 💡 **Recommended method:** via [HACS (Home Assistant Community Store)](https://hacs.xyz/)

### 🧩 Step-by-Step

1. **Add this repository** as a custom repository in HACS.  
   - Go to: `HACS → Integrations → Custom Repositories`  
   - Add the repository URL (this repo).
2. **Search for** `Ajax Integration Custom Plugin` in HACS.  
3. **Install** the integration from HACS.
4. **Restart Home Assistant** to apply changes.
5. Go to `Settings → Devices & Services → Add Integration`.
6. Search for **Ajax** and **authenticate** with your **dedicated Ajax account**.
7. Complete device customization in the UI.
8. 🎉 **Enjoy!**  
   Use your Ajax Alarm System directly in Home Assistant and create powerful automations and scripts.

---

## 🧰 Features

- 🔔 Arm, disarm, and trigger Ajax alarm modes.  
- 💡 Integrate alarm states into Home Assistant automations.  
- 📱 Customize notifications, triggers, and automations using Lovelace dashboards.  
- ⚙️ Simple configuration and automatic entity discovery.

---

## 🧠 Tips

- Combine this integration with **Home Assistant Automations** for:
  - Auto-arming when everyone leaves home.
  - Disarming when you arrive via geolocation.
  - Sending Telegram or mobile alerts on alarm triggers.

---

## 💬 Support & Feedback

If you encounter issues or have feature requests:
- Open an GitHub issues

---

## 🏷️ License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

### ❤️ Credits

Developed with care for the Home Assistant community.  
Secure. Private. Flexible.

> _“Automation should make your home smarter — not less secure.”_

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/66f4c5bc-3d72-4c22-b7aa-fe275904ec9d" />
