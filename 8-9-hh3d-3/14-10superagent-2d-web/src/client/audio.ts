export class AudioBus {
  private context: AudioContext | null = null;
  private master: GainNode | null = null;
  muted = localStorage.getItem('superagent-muted') === '1';

  unlock(): void {
    if (!this.context) {
      const AudioCtor = window.AudioContext ?? window.webkitAudioContext;
      if (!AudioCtor) return;
      this.context = new AudioCtor();
      this.master = this.context.createGain();
      this.master.gain.value = 0.12;
      this.master.connect(this.context.destination);
    }
    void this.context.resume();
  }

  tone(frequency: number, duration: number, type: OscillatorType = 'sine', gain = 0.08, slide = 0): void {
    if (this.muted || !this.context || !this.master) return;
    const now = this.context.currentTime;
    const oscillator = this.context.createOscillator();
    const envelope = this.context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, now);
    oscillator.frequency.exponentialRampToValueAtTime(Math.max(30, frequency + slide), now + duration);
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(gain, now + 0.008);
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    oscillator.connect(envelope).connect(this.master);
    oscillator.start(now);
    oscillator.stop(now + duration + 0.02);
  }

  noise(duration = 0.08, gain = 0.07): void {
    if (this.muted || !this.context || !this.master) return;
    const length = Math.max(1, Math.floor(this.context.sampleRate * duration));
    const buffer = this.context.createBuffer(1, length, this.context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
    const source = this.context.createBufferSource();
    const envelope = this.context.createGain();
    source.buffer = buffer;
    envelope.gain.setValueAtTime(gain, this.context.currentTime);
    envelope.gain.exponentialRampToValueAtTime(0.0001, this.context.currentTime + duration);
    source.connect(envelope).connect(this.master);
    source.start();
  }

  start(): void { this.tone(220, 0.18, 'sawtooth', 0.08, 360); this.tone(440, 0.28, 'triangle', 0.06, 220); }
  jump(): void { this.tone(260, 0.12, 'square', 0.045, 160); }
  shoot(): void { this.noise(0.045, 0.09); this.tone(125, 0.08, 'sawtooth', 0.045, -55); }
  hit(): void { this.tone(95, 0.11, 'square', 0.07, -35); this.noise(0.06, 0.035); }
  melee(): void { this.tone(180, 0.06, 'triangle', 0.05, 210); this.tone(420, 0.08, 'square', 0.025, -80); }
  grenade(): void { this.tone(130, 0.12, 'sawtooth', 0.04, 80); }
  land(): void { this.tone(78, 0.055, 'triangle', 0.028, -18); }
  pickup(): void { this.tone(620, 0.12, 'triangle', 0.05, 340); this.tone(930, 0.18, 'sine', 0.035, 100); }
  power(): void { this.tone(320, 0.18, 'triangle', 0.045, 520); this.tone(760, 0.24, 'sine', 0.035, 180); }
  explode(): void { this.noise(0.24, 0.14); this.tone(70, 0.24, 'sawtooth', 0.1, -40); }
  result(): void { this.tone(220, 0.16, 'triangle', 0.06, 220); this.tone(330, 0.24, 'triangle', 0.05, 330); this.tone(495, 0.34, 'sine', 0.04, 90); }
  toggleMute(): void { this.muted = !this.muted; localStorage.setItem('superagent-muted', this.muted ? '1' : '0'); if (this.master) this.master.gain.value = this.muted ? 0 : 0.12; }
}

