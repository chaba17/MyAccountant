import json
import os
import hashlib
import secrets
import streamlit as st

USERS_FILE = 'users.json'


def _hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with salt. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return hashed, salt


def _load_users() -> dict:
    """Load users from JSON file."""
    if not os.path.exists(USERS_FILE):
        # Create default admin user: admin / admin123
        default_hash, default_salt = _hash_password('admin123')
        users = {
            'admin': {
                'password_hash': default_hash,
                'salt': default_salt,
                'role': 'admin',
                'display_name': 'Administrator'
            }
        }
        _save_users(users)
        return users
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(users: dict):
    """Save users to JSON file."""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


def verify_login(username: str, password: str) -> bool:
    """Verify username and password."""
    users = _load_users()
    if username not in users:
        return False
    user = users[username]
    hashed, _ = _hash_password(password, user['salt'])
    return hashed == user['password_hash']


def get_user_role(username: str) -> str:
    """Get user role."""
    users = _load_users()
    return users.get(username, {}).get('role', 'user')


def get_display_name(username: str) -> str:
    """Get user display name."""
    users = _load_users()
    return users.get(username, {}).get('display_name', username)


def add_user(username: str, password: str, role: str = 'user', display_name: str = '') -> tuple:
    """Add a new user. Returns (success, message)."""
    if not username or not password:
        return False, "Username and password are required"
    if len(password) < 4:
        return False, "Password must be at least 4 characters"

    users = _load_users()
    if username in users:
        return False, f"User '{username}' already exists"

    hashed, salt = _hash_password(password)
    users[username] = {
        'password_hash': hashed,
        'salt': salt,
        'role': role,
        'display_name': display_name or username
    }
    _save_users(users)
    return True, f"User '{username}' created successfully"


def delete_user(username: str) -> tuple:
    """Delete a user. Returns (success, message)."""
    if username == 'admin':
        return False, "Cannot delete the admin user"
    users = _load_users()
    if username not in users:
        return False, f"User '{username}' not found"
    del users[username]
    _save_users(users)
    return True, f"User '{username}' deleted"


def change_password(username: str, new_password: str) -> tuple:
    """Change user password. Returns (success, message)."""
    if len(new_password) < 4:
        return False, "Password must be at least 4 characters"
    users = _load_users()
    if username not in users:
        return False, f"User '{username}' not found"
    hashed, salt = _hash_password(new_password)
    users[username]['password_hash'] = hashed
    users[username]['salt'] = salt
    _save_users(users)
    return True, "Password changed successfully"


def list_users() -> list:
    """List all users (without password info)."""
    users = _load_users()
    return [
        {'username': k, 'role': v['role'], 'display_name': v.get('display_name', k)}
        for k, v in users.items()
    ]


def login_page():
    """Render login page. Returns True if user is authenticated."""
    if st.session_state.get('authenticated'):
        return True

    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center;padding:40px 0 20px 0;">
            <div style="font-size:28px;font-weight:700;color:#0F172A;letter-spacing:-0.02em;">
                FinSuite Pro
            </div>
            <div style="font-size:13px;color:#94A3B8;margin-top:4px;">Financial Analysis Platform</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submitted:
                if verify_login(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_role = get_user_role(username)
                    st.session_state.display_name = get_display_name(username)
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        st.markdown("""
        <div style="text-align:center;margin-top:20px;font-size:12px;color:#94A3B8;">
            Contact administrator for access
        </div>
        """, unsafe_allow_html=True)

    return False


def render_admin_panel():
    """Render admin user management panel."""
    st.markdown("#### User Management")

    users = list_users()

    # Show existing users
    st.markdown("##### Current Users")
    for user in users:
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        c1.text(user['display_name'])
        c2.text(f"@{user['username']} ({user['role']})")

        if user['username'] != 'admin':
            if c3.button("Reset PW", key=f"reset_{user['username']}", use_container_width=True):
                st.session_state[f"resetting_{user['username']}"] = True

            if c4.button("Delete", key=f"del_{user['username']}", use_container_width=True):
                success, msg = delete_user(user['username'])
                if success:
                    st.toast(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            c3.text("")
            c4.text("(protected)")

        # Password reset form
        if st.session_state.get(f"resetting_{user['username']}"):
            new_pw = st.text_input(
                f"New password for {user['username']}:",
                type="password",
                key=f"newpw_{user['username']}"
            )
            rc1, rc2 = st.columns(2)
            if rc1.button("Save", key=f"savepw_{user['username']}", type="primary"):
                if new_pw:
                    success, msg = change_password(user['username'], new_pw)
                    if success:
                        st.toast(msg)
                        st.session_state[f"resetting_{user['username']}"] = False
                        st.rerun()
                    else:
                        st.error(msg)
            if rc2.button("Cancel", key=f"cancelpw_{user['username']}"):
                st.session_state[f"resetting_{user['username']}"] = False
                st.rerun()

    # Add new user
    st.markdown("---")
    st.markdown("##### Add New User")

    with st.form("add_user_form"):
        ac1, ac2 = st.columns(2)
        new_username = ac1.text_input("Username", placeholder="e.g. giorgi")
        new_display = ac2.text_input("Display Name", placeholder="e.g. Giorgi")
        ac3, ac4 = st.columns(2)
        new_password = ac3.text_input("Password", type="password")
        new_role = ac4.selectbox("Role", ["user", "admin"])

        if st.form_submit_button("Add User", type="primary", use_container_width=True):
            success, msg = add_user(new_username, new_password, new_role, new_display)
            if success:
                st.toast(msg)
                st.rerun()
            else:
                st.error(msg)

    # Change own password
    st.markdown("---")
    st.markdown("##### Change Admin Password")
    with st.form("change_admin_pw"):
        admin_new_pw = st.text_input("New admin password", type="password")
        if st.form_submit_button("Change Password"):
            if admin_new_pw:
                success, msg = change_password('admin', admin_new_pw)
                if success:
                    st.toast(msg)
                else:
                    st.error(msg)
