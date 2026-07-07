/*
 * WinCC Unified — Analog clock with date and digital time display
 * ================================================================
 *
 * SCREEN ITEMS REQUIRED (create these on your screen in TIA Portal):
 *
 *   Name             Type                     Notes
 *   ---------------  -----------------------  ------------------------------------
 *   HandHour         Line (or graphic view)   Drawn pointing straight UP (12 o'clock).
 *   HandMinute       Line (or graphic view)   Drawn pointing straight UP.
 *   HandSecond       Line (or graphic view)   Drawn pointing straight UP.
 *   TxtDigitalTime   Text box                 Shows HH:MM:SS.
 *   TxtDate          Text box                 Shows the date.
 *
 * IMPORTANT — rotation setup for each hand:
 *   In the Inspector window > Properties > Format, set the rotation
 *   center ("Rotation center X/Y") of each hand to its PIVOT point,
 *   i.e. the end of the line that sits at the middle of the clock face.
 *   All three hands must share that same pivot point on the screen.
 *   Draw a circle behind them for the dial; add tick marks as you like.
 *
 * WHERE THIS CODE GOES:
 *   1. The functions below   -> screen's "Global definition" script area.
 *   2. Screen "Loaded" event -> paste the body of onScreenLoaded().
 *   3. Screen "Cleared" event-> paste the body of onScreenCleared().
 *
 * Tested style targets TIA Portal V17+ (WinCC Unified PC / Comfort Panel).
 */

/* ------------------------------------------------------------------ */
/* Global definition area of the screen                                */
/* ------------------------------------------------------------------ */

let clockTimerId = null;

/**
 * Reads the current time and updates the three hands plus the
 * digital time and date text boxes. Called once per second.
 */
function updateClock() {
  const now = new Date();

  const h = now.getHours();
  const m = now.getMinutes();
  const s = now.getSeconds();

  // Angles in degrees, clockwise from 12 o'clock.
  // Hour hand also creeps with the minutes, minute hand with the seconds.
  const hourAngle   = (h % 12) * 30 + m * 0.5;
  const minuteAngle = m * 6 + s * 0.1;
  const secondAngle = s * 6;

  Screen.FindItem('HandHour').RotationAngle   = hourAngle;
  Screen.FindItem('HandMinute').RotationAngle = minuteAngle;
  Screen.FindItem('HandSecond').RotationAngle = secondAngle;

  // Digital display: HH:MM:SS (24 h). Change to 12 h below if preferred.
  const pad = (n) => String(n).padStart(2, '0');
  Screen.FindItem('TxtDigitalTime').Text = `${pad(h)}:${pad(m)}:${pad(s)}`;

  // Date display, e.g. "Mon 07.07.2026". Adjust format to taste.
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const dateText =
    `${days[now.getDay()]} ` +
    `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
  Screen.FindItem('TxtDate').Text = dateText;
}

/* 12-hour variant for the digital display, if you prefer AM/PM:
 *
 *   const h12 = h % 12 === 0 ? 12 : h % 12;
 *   const ampm = h < 12 ? 'AM' : 'PM';
 *   Screen.FindItem('TxtDigitalTime').Text =
 *     `${pad(h12)}:${pad(m)}:${pad(s)} ${ampm}`;
 */

/* ------------------------------------------------------------------ */
/* Screen event: Loaded                                                */
/* ------------------------------------------------------------------ */

function onScreenLoaded() {
  updateClock(); // paint immediately, don't wait for the first tick
  clockTimerId = HMIRuntime.Timers.SetInterval(updateClock, 1000);
}

/* ------------------------------------------------------------------ */
/* Screen event: Cleared                                               */
/* ------------------------------------------------------------------ */

function onScreenCleared() {
  if (clockTimerId !== null) {
    HMIRuntime.Timers.ClearInterval(clockTimerId);
    clockTimerId = null;
  }
}
