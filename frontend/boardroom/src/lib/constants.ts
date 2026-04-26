import type { CEOId } from './types'

export interface CompanyDef {
  id: CEOId
  name: string
  shortName: string      // ALL-CAPS short name for intel feed, event log, ticker
  ceoName: string        // Full formal name for portfolio cards
  ceoNickname: string    // Dramatic nickname for boardroom
  sector: string
  tagline: string
  color: string
}

// SATURATED brand colors — punchy against pure black
export const COMPANIES: CompanyDef[] = [
  { id: 'vermillion', name: 'CRIMSON & CO',       shortName: 'CRIMSON',   ceoName: 'Magnus Crane',        ceoNickname: 'THE WOLF',       sector: 'Finance',  tagline: 'Predator. Apex.',            color: '#FF0033' },
  { id: 'goldspire',  name: 'HELIOS LABS',        shortName: 'HELIOS',    ceoName: 'Dr. Yuki Solberg',    ceoNickname: 'SOLBERG',        sector: 'Tech',     tagline: 'Build. Disrupt. Repeat.',    color: '#FFD700' },
  { id: 'sablemark',  name: 'OBSIDIAN MEDIA',     shortName: 'OBSIDIAN',  ceoName: 'Vivienne Lazare',     ceoNickname: 'VIV',            sector: 'Media',    tagline: 'We own the narrative.',      color: '#A855F7' },
  { id: 'ironhold',   name: 'ATLAS FREIGHT',      shortName: 'ATLAS',     ceoName: 'Cyrus Volkov',        ceoNickname: 'VOLKOV',         sector: 'Shipping', tagline: 'The world moves through us.',color: '#64748B' },
  { id: 'ashen',      name: 'DRACO PETROLEUM',    shortName: 'DRACO',     ceoName: 'Hassan al-Rashid',    ceoNickname: 'AL-RASHID',      sector: 'Oil',      tagline: 'From earth, fire.',          color: '#FF6B2B' },
  { id: 'cobalt',     name: 'AZURE WIRELESS',     shortName: 'AZURE',     ceoName: 'Mei Chen-Whitfield',  ceoNickname: 'CHEN-WHITFIELD', sector: 'Telecom',  tagline: 'Connecting empires.',        color: '#3B82F6' },
  { id: 'verdant',    name: 'SERAPHIM BIOTECH',   shortName: 'SERAPHIM',  ceoName: 'Dr. Eitan Shoresh',   ceoNickname: 'SHORESH',        sector: 'Biotech',  tagline: 'Engineered to last.',        color: '#00E676' },
]

export const COMPANY_MAP = Object.fromEntries(
  COMPANIES.map((c) => [c.id, c])
) as Record<CEOId, CompanyDef>

export const CEO_IDS: CEOId[] = [
  'vermillion', 'goldspire', 'sablemark', 'ironhold', 'ashen', 'cobalt', 'verdant',
]

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const POLL_INTERVAL_MS = 1500
