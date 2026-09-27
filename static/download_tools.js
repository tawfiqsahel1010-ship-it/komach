(function () {
  function addButtons() {
    if (document.getElementById('downloadTools')) return;

    const box = document.createElement('div');
    box.id = 'downloadTools';
    box.style.cssText =
      'position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;gap:8px;';

    box.innerHTML =
      '<button id="dlImg" style="padding:10px;border:0;border-radius:8px;background:#198754;color:white;font-weight:bold">🖼️ دانلود عکس</button>' +
      '<button id="dlPdf" style="padding:10px;border:0;border-radius:8px;background:#dc3545;color:white;font-weight:bold">📄 دانلود PDF</button>';

    document.body.appendChild(box);

    document.getElementById('dlImg').onclick = async function () {
      if (!window.html2canvas) {
        alert('لطفاً چند لحظه صبر کنید و دوباره امتحان کنید.');
        return;
      }

      const canvas = await html2canvas(document.body, {
        scale: 2,
        backgroundColor: '#ffffff'
      });

      const a = document.createElement('a');
      a.download = 'report-' + new Date().toISOString().slice(0, 10) + '.png';
      a.href = canvas.toDataURL('image/png');
      a.click();
    };

    document.getElementById('dlPdf').onclick = function () {
      window.print();
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addButtons);
  } else {
    addButtons();
  }
})();
