// ABOUTME: GELATO Fulfillment screen (/gelato/fulfillment) — outbound pick/pack/ship
// ABOUTME: for a sales order (GELATO-02). Stub placeholder wired to the route + nav in
// ABOUTME: task 13; task 14 fleshes out the pick-list → pick → pack → ship flow.

/**
 * Fulfillment screen — GELATO outbound pick/pack/ship (/gelato/fulfillment).
 *
 * Placeholder introduced with the shipment hooks + nav link (task 13) so the route
 * compiles now; the pick-list, pick/pack/ship actions, and shipment detail land in
 * task 14 (GELATO-02, SC2–SC4).
 */
export default function Fulfillment() {
  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-semibold">Fulfillment</h1>
    </div>
  )
}
