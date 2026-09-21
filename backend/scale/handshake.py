"""The scale handshake as a state machine: given a scale frame, what to send back.

Mirrors the Fitdays app (#320): answer the hello with the guest record (which
sets the scale's clock), the user's profile and record, BD and the name offer;
acknowledge the result and any stored weigh-ins. No radio code: the caller
writes the returned frames to FFB1 in order.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from scale import name_image, protocol


@dataclass(frozen=True)
class ScaleProfile:
    height_cm: int
    age: int
    male: bool
    last_weight_kg: float | None
    prev_weight_kg: float | None
    target_weight_kg: float | None
    user_id: bytes


def _local_offset_min() -> int:
    return round(time.localtime().tm_gmtoff / 60)


class Handshake:
    def __init__(
        self,
        profile: ScaleProfile,
        now: Callable[[], int] = lambda: int(time.time()),
        utc_offset_min: int | None = None,
        *,
        seq: int = 0,
        sent_sequence: bool = False,
        name: str | None = None,
    ) -> None:
        """`seq` and `sent_sequence` resume a handshake whose state the phone
        carried between requests (#323); a fresh one starts at 0, unsent."""
        self.profile = profile
        # With a name, offer our own image of it (#324); without, replay the
        # captured offer, which keeps whatever name the scale already shows.
        self.image = name_image.render(name) if name else None
        self._image_chunks: list[bytes] = []
        self.now = now
        self.utc_offset_min = (
            _local_offset_min() if utc_offset_min is None else utc_offset_min
        )
        self.seq = seq
        self.sent_sequence = sent_sequence
        self.result: protocol.Measurement | None = None
        self.stored: list[protocol.Measurement] = []

    def _next(self) -> int:
        seq, self.seq = self.seq, self.seq + 1
        return seq

    def _sequence(self) -> list[bytes]:
        p, t = self.profile, self.now()
        self.sent_sequence = True
        return [
            protocol.guest_record(
                self._next(), unix_time=t, utc_offset_min=self.utc_offset_min
            ),
            protocol.profile(
                self._next(),
                height_cm=p.height_cm,
                last_weight_kg=p.last_weight_kg,
                male=p.male,
                age=p.age,
                user_id=p.user_id,
            ),
            protocol.user_record(
                self._next(),
                unix_time=t,
                utc_offset_min=self.utc_offset_min,
                height_cm=p.height_cm,
                last_weight_kg=p.last_weight_kg,
                male=p.male,
                age=p.age,
                prev_weight_kg=p.prev_weight_kg,
                target_weight_kg=p.target_weight_kg,
                user_id=p.user_id,
            ),
            protocol.bd(self._next()),
            self._name_offer(p.user_id),
        ]

    def _name_offer(self, user_id: bytes) -> bytes:
        if self.image is None:
            return protocol.bc(self._next(), user_id=user_id)
        return protocol.name_offer(
            self._next(),
            image=self.image,
            user_id=user_id,
            image_id=name_image.image_id(self.image),
        )

    def start(self) -> list[bytes]:
        """The sequence, unprompted — for when the hello came before the phone listened."""
        return [] if self.sent_sequence else self._sequence()

    def on_scale_frame(self, f: protocol.Frame) -> list[bytes]:
        if f.type == 0xAA:  # hello
            out = [protocol.ack(self._next(), f.seq)]
            return out if self.sent_sequence else out + self._sequence()
        if f.type == protocol.RESULT:
            self.result = protocol.decode_measurement(f)
            return [protocol.ack(self._next(), f.seq)]
        if f.type == protocol.STORED:  # re-offered every ~10 s until acknowledged
            record = protocol.decode_measurement(f)
            if all(r.timestamp != record.timestamp for r in self.stored):
                self.stored.append(record)
            return [protocol.ack(self._next(), f.seq)]
        if f.type == 0xAD and self.image is not None and f.payload[:2] == b"\x01\x00":
            # The scale wants the image; its reply names the chunk length.
            chunk_len = f.payload[4] if len(f.payload) > 4 else 149
            self._image_chunks = name_image.chunks(self.image, chunk_len=chunk_len)
        return []

    def take_image_chunks(self) -> list[bytes]:
        """FFB4 writes due since the scale asked for the name image; handed out once."""
        out, self._image_chunks = self._image_chunks, []
        return out
