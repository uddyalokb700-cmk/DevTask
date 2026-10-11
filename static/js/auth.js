/**
 * Client authentication handlers for Login & Registration
 */

document.addEventListener('DOMContentLoaded', () => {
  // Password visibility toggle helper
  document.querySelectorAll('.toggle-password-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      const icon = btn.querySelector('i');
      if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'bi bi-eye-slash';
      } else {
        input.type = 'password';
        icon.className = 'bi bi-eye';
      }
    });
  });

  // Login Form Submission
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = loginForm.querySelector('button[type="submit"]');
      const errBox = document.getElementById('authErrorBox');
      errBox.classList.add('d-none');
      errBox.textContent = '';

      const username = document.getElementById('username').value.trim();
      const password = document.getElementById('password').value;

      if (!username || !password) {
        errBox.textContent = 'Please enter both username and password.';
        errBox.classList.remove('d-none');
        return;
      }

      const originalBtnText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Signing in...';

      try {
        await apiRequest('/api/auth/login/', {
          method: 'POST',
          body: { username, password }
        });
        showToast('Signed in successfully!', 'success');
        window.location.href = '/dashboard/';
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
        errBox.textContent = err.message || 'Authentication failed. Please check credentials.';
        errBox.classList.remove('d-none');
      }
    });
  }

  // Registration Form Submission
  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = registerForm.querySelector('button[type="submit"]');
      const errBox = document.getElementById('authErrorBox');
      errBox.classList.add('d-none');
      errBox.textContent = '';

      const username = document.getElementById('username').value.trim();
      const email = document.getElementById('email').value.trim();
      const displayName = document.getElementById('displayName').value.trim();
      const password = document.getElementById('password').value;
      const passwordConfirm = document.getElementById('passwordConfirm').value;

      if (password !== passwordConfirm) {
        errBox.textContent = 'Passwords do not match.';
        errBox.classList.remove('d-none');
        return;
      }

      if (password.length < 8) {
        errBox.textContent = 'Password must be at least 8 characters long.';
        errBox.classList.remove('d-none');
        return;
      }

      const originalBtnText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating account...';

      try {
        await apiRequest('/api/auth/register/', {
          method: 'POST',
          body: {
            username,
            email,
            display_name: displayName,
            password,
            password_confirm: passwordConfirm
          }
        });
        showToast('Account created successfully!', 'success');
        window.location.href = '/dashboard/';
      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
        errBox.textContent = err.message || 'Registration failed. Please review errors.';
        errBox.classList.remove('d-none');
      }
    });
  }
});
