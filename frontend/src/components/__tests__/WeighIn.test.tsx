import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WeighIn from '../WeighIn'
import * as features from '../../api/features'
import * as relay from '../../scale/relay'

/**
 * The Weigh-in button (#322). Opt-in (#326): it only appears when the backend
 * reports the scale feature on. It needs Web Bluetooth, which Safari, every
 * other iOS browser and Firefox lack — there it explains, and names Bluefy.
 */

vi.mock('../../scale/relay', () => ({ weighIn: vi.fn() }))

const MEASUREMENT = { id: 7, weight_kg: 72.5, body_fat_pct: 18.5 }

function setBluetooth(present: boolean) {
  Object.defineProperty(navigator, 'bluetooth', {
    configurable: true,
    value: present ? { requestDevice: vi.fn() } : undefined,
  })
}

function renderIt(onMeasured = vi.fn()) {
  render(<MemoryRouter><WeighIn onMeasured={onMeasured} /></MemoryRouter>)
  return onMeasured
}

beforeEach(() => {
  vi.spyOn(features, 'getFeatures').mockResolvedValue({ scale: true })
  setBluetooth(true)
})

afterEach(() => {
  vi.restoreAllMocks()
  setBluetooth(false)
})

describe('visibility', () => {
  it('shows nothing while the scale feature is off', async () => {
    vi.mocked(features.getFeatures).mockResolvedValue({ scale: false })
    renderIt()
    await waitFor(() => expect(features.getFeatures).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: /weigh in/i })).toBeNull()
    expect(screen.queryByText(/bluefy/i)).toBeNull()
  })

  it('shows nothing if the feature check fails', async () => {
    vi.mocked(features.getFeatures).mockRejectedValue(new Error('offline'))
    renderIt()
    await waitFor(() => expect(features.getFeatures).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: /weigh in/i })).toBeNull()
  })

  it('offers the button when the feature is on and the browser has Web Bluetooth', async () => {
    renderIt()
    expect(await screen.findByRole('button', { name: /weigh in/i })).toBeInTheDocument()
  })

  it('explains, and names Bluefy, when the browser has no Web Bluetooth', async () => {
    setBluetooth(false)
    renderIt()
    expect(await screen.findByText(/bluefy/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /weigh in/i })).toBeNull()
  })
})

describe('weighing in', () => {
  it('shows live weight, then the stored result, and hands it to the page', async () => {
    vi.mocked(relay.weighIn).mockImplementation(async ({ onLiveWeight }) => {
      onLiveWeight?.(72.3)
      return MEASUREMENT as never
    })
    const onMeasured = renderIt()
    fireEvent.click(await screen.findByRole('button', { name: /weigh in/i }))
    expect(await screen.findByText(/72\.5 kg/)).toBeInTheDocument()
    expect(screen.getByText(/18\.5 %/)).toBeInTheDocument()
    expect(onMeasured).toHaveBeenCalledWith(MEASUREMENT)
  })

  it('sends the phone’s UTC offset', async () => {
    vi.mocked(relay.weighIn).mockResolvedValue(MEASUREMENT as never)
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: /weigh in/i }))
    await waitFor(() => expect(relay.weighIn).toHaveBeenCalled())
    expect(vi.mocked(relay.weighIn).mock.calls[0]![0].utcOffsetMin).toBe(-new Date().getTimezoneOffset())
  })

  it('links to the profile when it is incomplete', async () => {
    vi.mocked(relay.weighIn).mockRejectedValue(new Error('Complete your profile before weighing in: height'))
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: /weigh in/i }))
    expect(await screen.findByText(/complete your profile/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /profile/i })).toHaveAttribute('href', '/settings')
  })

  it('shows other failures and lets the user try again', async () => {
    vi.mocked(relay.weighIn).mockRejectedValue(new Error('Lost connection to the scale.'))
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: /weigh in/i }))
    expect(await screen.findByText(/lost connection/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /weigh in/i })).not.toBeDisabled()
  })

  it('disables the button while a weigh-in is running', async () => {
    vi.mocked(relay.weighIn).mockReturnValue(new Promise(() => {}))
    renderIt()
    const button = await screen.findByRole('button', { name: /weigh in/i })
    fireEvent.click(button)
    await waitFor(() => expect(button).toBeDisabled())
  })
})
