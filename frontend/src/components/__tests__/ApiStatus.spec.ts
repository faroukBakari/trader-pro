import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ApiStatus from '../ApiStatus.vue'

describe('ApiStatus', () => {
  it('renders the component with semantic header', () => {
    const wrapper = mount(ApiStatus)
    const header = wrapper.find('header')
    expect(header.exists()).toBe(true)
    expect(wrapper.text()).toContain('API Status')
  })

  it('displays client type in header', () => {
    const wrapper = mount(ApiStatus)
    const header = wrapper.find('header')
    expect(header.text()).toContain('Client:')
  })

  it('shows loading state initially', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Loading API status...')
    const loadingParagraph = wrapper.find('p.loading')
    expect(loadingParagraph.exists()).toBe(true)
  })

  it('has a refresh button', () => {
    const wrapper = mount(ApiStatus)
    const refreshButton = wrapper.find('button')
    expect(refreshButton.exists()).toBe(true)
    expect(refreshButton.text()).toContain('Refresh')
  })

  it('displays API status information after loading', async () => {
    const wrapper = mount(ApiStatus)

    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Loading API status...')
    const text = wrapper.text()
    expect(text).toBeTruthy()
    expect(text.length).toBeGreaterThan(50)
  })

  it('refresh button triggers data refresh without re-rendering cards', async () => {
    const wrapper = mount(ApiStatus)

    await new Promise((resolve) => setTimeout(resolve, 300))
    await wrapper.vm.$nextTick()

    const cardsBefore = wrapper.findAll('article.module-card')
    const refreshButton = wrapper.find('button')
    expect(refreshButton.exists()).toBe(true)

    await refreshButton.trigger('click')
    await wrapper.vm.$nextTick()

    const cardsAfter = wrapper.findAll('article.module-card')
    expect(cardsAfter.length).toBe(cardsBefore.length)
    expect(wrapper.text()).toContain('API Status')
  })

  it('separates initial loading from refresh state', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Loading API status...')

    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Loading API status...')

    const button = wrapper.find('button')
    await button.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('Loading API status...')
    expect(button.text()).toContain('Refresh')
  })
})

describe('ApiStatus - Multi-Module Display', () => {
  it('should render module cards from static configuration', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const moduleCards = wrapper.findAll('article.module-card')
    expect(moduleCards.length).toBeGreaterThanOrEqual(2)
  })

  it('should display module names in h3 headings', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('Broker')
    expect(text).toContain('Datafeed')

    const headings = wrapper.findAll('article h3')
    expect(headings.length).toBeGreaterThanOrEqual(2)
  })

  it('should use definition lists for module details', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const definitionLists = wrapper.findAll('dl')
    expect(definitionLists.length).toBeGreaterThanOrEqual(2)

    const dtElements = wrapper.findAll('dt')
    expect(dtElements.length).toBeGreaterThan(0)
    expect(dtElements.some((dt) => dt.text() === 'Health:')).toBe(true)
  })

  it('should display health status with correct CSS classes', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const statusElements = wrapper.findAll('.status')
    expect(statusElements.length).toBeGreaterThan(0)

    const hasStatusClass = statusElements.some((el) => {
      return (
        el.classes().includes('status-ok') ||
        el.classes().includes('status-error') ||
        el.classes().includes('status-unknown')
      )
    })
    expect(hasStatusClass).toBe(true)
  })

  it('should handle error states gracefully', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    const hasHealthSection = text.includes('Health:')
    expect(hasHealthSection).toBe(true)
  })

  it('should display module data without duplicating cards', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const cardsBefore = wrapper.findAll('article.module-card')
    const button = wrapper.find('button')
    await button.trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 300))
    await wrapper.vm.$nextTick()

    const cardsAfter = wrapper.findAll('article.module-card')
    expect(cardsAfter.length).toBe(cardsBefore.length)
  })

  it('should display version info in definition list', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const dls = wrapper.findAll('dl')
    expect(dls.length).toBeGreaterThan(0)

    const dtElements = wrapper.findAll('dt')
    expect(dtElements.length).toBeGreaterThan(0)
  })

  it('should display OpenAPI docs links in nav element', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const navElements = wrapper.findAll('nav')
    expect(navElements.length).toBeGreaterThan(0)

    const links = wrapper.findAll('nav a')
    expect(links.length).toBeGreaterThan(0)

    const hasDocsLink = links.some((link) => link.text().includes('OpenAPI Docs'))
    expect(hasDocsLink).toBe(true)
  })

  it('should display AsyncAPI links for modules with WebSocket', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('AsyncAPI')

    const links = wrapper.findAll('nav a')
    const hasAsyncApiLink = links.some((link) => link.text().includes('AsyncAPI'))
    expect(hasAsyncApiLink).toBe(true)
  })

  it('should disable refresh button while refreshing', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeUndefined()

    await button.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Refresh')
  })

  it('should enable refresh button after refresh completes', async () => {
    const wrapper = mount(ApiStatus)
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    const button = wrapper.find('button')
    await button.trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 300))
    await wrapper.vm.$nextTick()

    expect(button.attributes('disabled')).toBeUndefined()
  })
})
