import defaultMdxComponents from 'fumadocs-ui/mdx';
import { Accordion, Accordions } from 'fumadocs-ui/components/accordion';
import { Step, Steps } from 'fumadocs-ui/components/steps';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import { TypeTable } from 'fumadocs-ui/components/type-table';
import {
  ArrowFlipDiagram,
  CascadeDiagram,
  RingsDiagram,
  SeamDiagram,
  TangleDiagram,
} from '@/components/article/diagrams';
import type { MDXComponents } from 'mdx/types';

export function getMDXComponents(components?: MDXComponents) {
  return {
    ...defaultMdxComponents,
    Accordion,
    Accordions,
    ArrowFlipDiagram,
    CascadeDiagram,
    RingsDiagram,
    SeamDiagram,
    Step,
    Steps,
    Tab,
    Tabs,
    TangleDiagram,
    TypeTable,
    ...components,
  } satisfies MDXComponents;
}

export const useMDXComponents = getMDXComponents;

declare global {
  type MDXProvidedComponents = ReturnType<typeof getMDXComponents>;
}
