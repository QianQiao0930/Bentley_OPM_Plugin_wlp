using System;
using System.Windows;
using System.Windows.Controls;

namespace SteelSectionProbe
{
    internal partial class HomePage : UserControl
    {
        internal event Action<string> FeatureRequested;

        internal HomePage()
        {
            InitializeComponent();
        }

        private void ComponentProperties_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("component-properties");
        }

        private void ElbowTrunnion_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("elbow-trunnion");
        }

        private void SupportStatistics_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("support-statistics");
        }
        private void Nozzle_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("solid-nozzle");
        }
        private void TankManhole_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("tank-manhole");
        }
        private void PipeClamp_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("pipe-clamp");
        }
        private void G2Anchor_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("g2-anchor-plate");
        }
        private void SteelSection_Click(object sender, RoutedEventArgs e)
        {
            if (FeatureRequested != null) FeatureRequested("steel-sections");
        }
    }
}

