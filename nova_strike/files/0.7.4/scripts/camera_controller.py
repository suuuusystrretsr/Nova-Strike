import random

from ursina import Vec3, camera, distance, lerp, raycast, scene

from scripts.utils import lerp_vec3


class CameraController:
    def __init__(self, player, game_manager) -> None:
        self.player = player
        self.game_manager = game_manager
        self.rng = getattr(game_manager, "rng", random)
        self.mode = "first_person"

        self.first_person_distance = 0.05
        self.first_person_position_smooth = 24.0
        self.first_person_rotation_smooth = 23.0

        self.third_person_distance = 8.8
        self.third_person_height = 2.35
        self.third_person_shoulder_offset = 1.85
        self.third_person_position_smooth = 11.0
        self.third_person_rotation_smooth = 14.0

        self.shake_intensity = 0.0
        self.shake_decay = 8.2
        self.shake_roll = 0.0

    def toggle_mode(self) -> None:
        self.mode = "third_person" if self.mode == "first_person" else "first_person"

    def add_shake(self, amount: float) -> None:
        self.shake_intensity = min(2.4, self.shake_intensity + max(0.0, amount))
        self.shake_roll += self.rng.uniform(-1.0, 1.0) * amount

    def update(self) -> None:
        if self.game_manager.state != "playing" or not self.player or not self.player.alive:
            return

        dt = max(0.0, float(getattr(self.game_manager, "frame_dt", 1.0 / 60.0)))
        settings = self.game_manager.settings_manager
        base_fov = settings.get_fov()
        sprint_bonus = 2.5 if self.player.is_moving and self.player.is_sprinting else 0.0
        target_fov = base_fov if self.mode == "first_person" else max(68, base_fov - 6.0)
        target_fov += sprint_bonus

        head_position = self.player.world_position + Vec3(0, self.player.camera_height, 0)
        target_rotation = Vec3(self.player.pitch, self.player.rotation_y, 0)

        if self.mode == "first_person":
            desired_position = head_position + self.player.forward * self.first_person_distance
            self.player.set_first_person(True)
            position_smooth = self.first_person_position_smooth
            rotation_smooth = self.first_person_rotation_smooth
        else:
            self.player.set_first_person(False)
            position_smooth = self.third_person_position_smooth
            rotation_smooth = self.third_person_rotation_smooth
            desired_position = self._compute_third_person_position(head_position)

        shake_vector, shake_rot = self._compute_camera_shake(dt)
        desired_position += shake_vector
        target_rotation.x += shake_rot.x
        target_rotation.y += shake_rot.y

        camera.fov = lerp(camera.fov, target_fov, min(1.0, dt * 7.0))
        position_blend = min(1.0, dt * position_smooth)
        rotation_blend = min(1.0, dt * rotation_smooth)
        camera.world_position = lerp_vec3(camera.world_position, desired_position, position_blend)
        camera.rotation_x = lerp(camera.rotation_x, target_rotation.x, rotation_blend)
        camera.rotation_y = lerp(camera.rotation_y, target_rotation.y, rotation_blend)
        camera.rotation_z = lerp(camera.rotation_z, self.shake_roll * 0.35, min(1.0, dt * 9.0))

    def _compute_third_person_position(self, head_position: Vec3) -> Vec3:
        raw_third_pos = (
            head_position
            - self.player.forward * self.third_person_distance
            + Vec3(0, self.third_person_height, 0)
            + self.player.right * self.third_person_shoulder_offset
        )
        to_cam = raw_third_pos - head_position
        if to_cam.length() <= 0.001:
            to_cam = Vec3(0, 0, -1)

        world_root = self.game_manager.world.root if self.game_manager.world and self.game_manager.world.root else scene
        ignore_targets = [self.player]
        ignore_targets.extend(self.game_manager.enemies)
        ignore_targets.extend(self.game_manager.npcs)
        ignore_targets.extend(self.game_manager.pickups)
        block_ray = raycast(
            head_position + Vec3(0, 0.25, 0),
            to_cam.normalized(),
            distance=distance(head_position, raw_third_pos),
            ignore=ignore_targets,
            traverse_target=world_root,
        )
        if not block_ray.hit:
            return raw_third_pos

        safe_pos = block_ray.world_point + block_ray.normal * 0.65
        min_offset = 2.6
        current_offset = distance(head_position, safe_pos)
        if current_offset < min_offset:
            safe_pos = head_position - self.player.forward * min_offset + Vec3(0, 0.9, 0)
        return safe_pos

    def _compute_camera_shake(self, dt: float):
        self.shake_intensity = max(0.0, self.shake_intensity - self.shake_decay * dt)
        self.shake_roll = lerp(self.shake_roll, 0.0, min(1.0, dt * 6.0))
        if self.shake_intensity <= 0.001:
            return Vec3(0, 0, 0), Vec3(0, 0, 0)

        x = self.rng.uniform(-0.012, 0.012) * self.shake_intensity
        y = self.rng.uniform(-0.012, 0.012) * self.shake_intensity
        z = self.rng.uniform(-0.01, 0.01) * self.shake_intensity
        pitch = self.rng.uniform(-0.6, 0.6) * self.shake_intensity
        yaw = self.rng.uniform(-0.7, 0.7) * self.shake_intensity
        self.shake_roll += self.rng.uniform(-0.5, 0.5) * self.shake_intensity
        return Vec3(x, y, z), Vec3(pitch, yaw, 0)
