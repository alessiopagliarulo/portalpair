document.addEventListener('DOMContentLoaded', async () => {
  const user = await checkAuth();
  if (user?.email) {
    window.location.href = 'dashboard.html';
    return;
  }

  const stepEmail = document.getElementById('stepEmail');
  const stepCode = document.getElementById('stepCode');
  const emailInput = document.getElementById('emailInput');
  const codeInput = document.getElementById('codeInput');
  const emailError = document.getElementById('emailError');
  const codeError = document.getElementById('codeError');
  const emailDisplay = document.getElementById('emailDisplay');
  const sendCodeBtn = document.getElementById('sendCodeBtn');
  const verifyBtn = document.getElementById('verifyBtn');

  function showEmailError(msg) {
    emailError.textContent = msg || '';
    emailError.classList.toggle('hidden', !msg);
    emailInput?.classList.toggle('invalid', !!msg);
  }
  function showCodeError(msg) {
    codeError.textContent = msg || '';
    codeError.classList.toggle('hidden', !msg);
    codeInput?.classList.toggle('invalid', !!msg);
  }
  function isEdu(email) {
    const d = (email || '').trim().toLowerCase().split('@')[1] || '';
    return d.endsWith('.edu');
  }

  sendCodeBtn?.addEventListener('click', async () => {
    showEmailError('');
    const email = emailInput?.value?.trim();
    if (!email || !email.includes('@')) {
      showEmailError('Please enter a valid email.');
      return;
    }
    if (!isEdu(email)) {
      showEmailError('Only .edu email addresses are accepted.');
      return;
    }
    sendCodeBtn.disabled = true;
    try {
      await sendCode(email);
      emailDisplay.textContent = email;
      stepEmail.classList.add('hidden');
      stepCode.classList.remove('hidden');
      codeInput.value = '';
      codeInput.focus();
    } catch (err) {
      showEmailError(err.message || 'Failed to send code.');
    } finally {
      sendCodeBtn.disabled = false;
    }
  });

  verifyBtn?.addEventListener('click', async () => {
    showCodeError('');
    const email = emailInput?.value?.trim();
    const code = codeInput?.value?.trim();
    if (!code) {
      showCodeError('Enter the verification code.');
      return;
    }
    verifyBtn.disabled = true;
    try {
      const data = await verifyCode(email, code);
      window.location.href = data.redirect || 'dashboard.html';
    } catch (err) {
      showCodeError(err.message || 'Invalid code. Try again.');
    } finally {
      verifyBtn.disabled = false;
    }
  });

  codeInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') verifyBtn?.click();
  });
});
