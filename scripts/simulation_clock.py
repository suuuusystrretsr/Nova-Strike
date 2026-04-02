class SimulationClock:
    """
    Fixed-step simulation clock.

    Keeps simulation deterministic-ish and stable across FPS differences by
    advancing gameplay in fixed substeps while still tracking render/frame dt.
    """

    def __init__(self, fixed_dt: float = 1.0 / 60.0, max_frame_dt: float = 0.1, max_substeps: int = 5) -> None:
        self.fixed_dt = max(1e-4, float(fixed_dt))
        self.max_frame_dt = max(self.fixed_dt, float(max_frame_dt))
        self.max_substeps = max(1, int(max_substeps))
        self.accumulator = 0.0
        self.frame_dt = self.fixed_dt

    def begin_frame(self, raw_dt: float) -> float:
        dt = float(raw_dt) if raw_dt is not None else self.fixed_dt
        if dt <= 0.0:
            dt = self.fixed_dt
        dt = min(dt, self.max_frame_dt)
        self.frame_dt = dt
        self.accumulator += dt
        return dt

    def consume_steps(self) -> int:
        steps = int(self.accumulator / self.fixed_dt)
        if steps <= 0:
            return 0
        if steps > self.max_substeps:
            # Drop runaway accumulated time to avoid "spiral of death".
            steps = self.max_substeps
            self.accumulator = 0.0
            return steps
        self.accumulator -= steps * self.fixed_dt
        return steps

