/* 
 * File:   MyCursor.h
 * Author: a22543
 *
 * Created on October 1, 2012, 11:28 AM
 */

#ifndef MYCURSOR_H
#define	MYCURSOR_H

#include <wx/wx.h>
#include "mathplot.h"

class MyCursor : public mpFY
{
    double m_x;
public:
    MyCursor(double x, wxString name) : mpFY(name)
    {
        m_x = x;
    }
    virtual double GetX(double y) {return m_x;}
    virtual double GetMaxY() {return 1024;}
    virtual double GetMinY() {return 0;}
    void move(double x);
    double getP() {return m_x;}
};

#endif	/* MYCURSOR_H */

